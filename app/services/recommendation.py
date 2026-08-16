from __future__ import annotations

import json
import logging
from typing import List, Optional

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.redis import CacheKeys
from app.models.product import Product
from app.models.user import UserProductInteraction

logger = logging.getLogger(__name__)

# Recommendation weight blend
CF_WEIGHT = 0.6
CBF_WEIGHT = 0.4


class RecommendedItem:
    def __init__(self, product_id: str, score: float, reason: str):
        self.product_id = product_id
        self.score = score
        self.reason = reason


class RecommendationService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis):
        self.db = db
        self.redis = redis

    async def get_recommendations(
        self,
        user_id: str,
        limit: int = 10,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[RecommendedItem]:
        """
        Main entry point. Returns ranked list of recommended products.
        Falls back to popularity if user has insufficient history.
        """
        # Check Redis cache first
        cache_key = CacheKeys.recommendations(user_id)
        cached = await self.redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            recs = [RecommendedItem(**d) for d in data]
        else:
            # Check interaction count for cold-start detection
            count_result = await self.db.execute(
                select(func.count(UserProductInteraction.id)).where(
                    UserProductInteraction.user_id == user_id
                )
            )
            interaction_count = count_result.scalar() or 0

            if interaction_count < settings.min_interactions_for_cf:
                recs = await self._popularity_recommendations(user_id, limit * 2)
            else:
                cf_recs = await self._collaborative_filtering(user_id, limit * 2)
                cbf_recs = await self._content_based_filtering(user_id, limit * 2)
                recs = self._blend_recommendations(cf_recs, cbf_recs, limit * 2)

            # Cache results
            await self.redis.setex(
                cache_key,
                settings.recommendation_cache_ttl,
                json.dumps(
                    [
                        {"product_id": r.product_id, "score": r.score, "reason": r.reason}
                        for r in recs
                    ]
                ),
            )

        # Filter exclusions and apply limit
        exclude_set = set(exclude_ids or [])
        filtered = [r for r in recs if r.product_id not in exclude_set]
        return filtered[:limit]

    async def _collaborative_filtering(
        self, user_id: str, limit: int
    ) -> List[RecommendedItem]:
        """
        SVD-based collaborative filtering.

        Builds a sparse user-item matrix from interaction weights,
        decomposes it with TruncatedSVD, reconstructs scores, and ranks
        items the target user hasn't interacted with.
        """
        try:
            from sklearn.decomposition import TruncatedSVD

            # Load all interactions
            result = await self.db.execute(
                select(
                    UserProductInteraction.user_id,
                    UserProductInteraction.product_id,
                    func.sum(UserProductInteraction.weight).label("total_weight"),
                ).group_by(
                    UserProductInteraction.user_id,
                    UserProductInteraction.product_id,
                )
            )
            rows = result.all()

            if not rows:
                return []

            # Build index maps
            users = list({r.user_id for r in rows})
            products = list({r.product_id for r in rows})
            u_idx = {u: i for i, u in enumerate(users)}
            p_idx = {p: i for i, p in enumerate(products)}

            # Build dense matrix
            matrix = np.zeros((len(users), len(products)), dtype=np.float32)
            for row in rows:
                matrix[u_idx[row.user_id], p_idx[row.product_id]] = float(
                    row.total_weight
                )

            if user_id not in u_idx:
                return []

            # SVD decomposition
            n_components = min(20, min(matrix.shape) - 1)
            if n_components < 1:
                return []

            svd = TruncatedSVD(n_components=n_components, random_state=42)
            user_factors = svd.fit_transform(matrix)
            item_factors = svd.components_.T  # shape: (n_products, n_components)

            # Reconstruct scores for our user
            user_vec = user_factors[u_idx[user_id]]
            scores = item_factors @ user_vec

            # Items the user already interacted with
            seen_result = await self.db.execute(
                select(UserProductInteraction.product_id).where(
                    UserProductInteraction.user_id == user_id
                )
            )
            seen = {r.product_id for r in seen_result.all()}

            # Rank unseen items
            ranked = sorted(
                [
                    (products[i], float(scores[i]))
                    for i in range(len(products))
                    if products[i] not in seen
                ],
                key=lambda x: x[1],
                reverse=True,
            )

            return [
                RecommendedItem(pid, score, "collaborative")
                for pid, score in ranked[:limit]
            ]

        except Exception as e:
            logger.warning(f"CF recommendation failed: {e}")
            return []

    async def _content_based_filtering(
        self, user_id: str, limit: int
    ) -> List[RecommendedItem]:
        """
        Content-based filtering using TF-IDF vectoriser + cosine similarity.

        1. Build TF-IDF matrix from product name + description + tags + category
        2. Construct a weighted user profile from interacted products
        3. Score all unseen products by cosine similarity to the profile
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            # Get user's interacted products (weighted by interaction strength)
            seen_result = await self.db.execute(
                select(
                    UserProductInteraction.product_id,
                    func.sum(UserProductInteraction.weight).label("w"),
                )
                .where(UserProductInteraction.user_id == user_id)
                .group_by(UserProductInteraction.product_id)
                .order_by(func.sum(UserProductInteraction.weight).desc())
                .limit(20)
            )
            seen_rows = seen_result.all()
            if not seen_rows:
                return []

            seen_ids = [r.product_id for r in seen_rows]
            seen_weights = np.array([float(r.w) for r in seen_rows])

            # Fetch text for seen products
            seen_prods_result = await self.db.execute(
                select(Product.id, Product.name, Product.description, Product.tags)
                .where(Product.id.in_(seen_ids))
            )
            seen_text_map = {
                r.id: f"{r.name} {r.description or ''} {r.tags or ''}"
                for r in seen_prods_result.all()
            }

            # Fetch candidate products (not seen by user)
            cands_result = await self.db.execute(
                select(Product.id, Product.name, Product.description, Product.tags)
                .where(Product.is_active == True, Product.id.notin_(seen_ids))
                .limit(500)
            )
            cands_rows = cands_result.all()
            if not cands_rows:
                return []

            cand_ids = [r.id for r in cands_rows]
            cand_text_map = {
                r.id: f"{r.name} {r.description or ''} {r.tags or ''}"
                for r in cands_rows
            }

            # Build corpus for TF-IDF: seen products first, then candidates
            seen_texts = [seen_text_map.get(sid, "") for sid in seen_ids]
            cand_texts = [cand_text_map[cid] for cid in cand_ids]
            all_texts = seen_texts + cand_texts

            # Fit TF-IDF on entire corpus
            vectorizer = TfidfVectorizer(
                max_features=5000,
                stop_words="english",
                ngram_range=(1, 2),
                sublinear_tf=True,
            )
            tfidf_matrix = vectorizer.fit_transform(all_texts)

            seen_matrix = tfidf_matrix[: len(seen_texts)]
            cand_matrix = tfidf_matrix[len(seen_texts):]

            # Weighted mean of user preference profile
            seen_weights_norm = seen_weights / seen_weights.sum()
            profile_vector = seen_matrix.T.dot(seen_weights_norm)  # sparse-safe
            profile_matrix = profile_vector.T  # shape (1, n_features)

            # Cosine similarity between profile and all candidates
            sims = cosine_similarity(profile_matrix, cand_matrix)[0]

            ranked = sorted(
                zip(cand_ids, sims.tolist()), key=lambda x: x[1], reverse=True
            )

            return [
                RecommendedItem(pid, float(score), "content_based")
                for pid, score in ranked[:limit]
            ]

        except Exception as e:
            logger.warning(f"CBF recommendation failed: {e}")
            return []

    async def _popularity_recommendations(
        self, user_id: str, limit: int
    ) -> List[RecommendedItem]:
        """Cold-start fallback — return most popular products."""
        result = await self.db.execute(
            select(Product.id, Product.sold_count, Product.average_rating)
            .where(Product.is_active == True)
            .order_by(
                (Product.sold_count * 0.7 + Product.average_rating * 10 * 0.3).desc()
            )
            .limit(limit)
        )
        rows = result.all()
        if not rows:
            return []
        max_score = max(
            (r.sold_count + r.average_rating * 10 for r in rows), default=1
        )
        return [
            RecommendedItem(
                r.id,
                round((r.sold_count + r.average_rating * 10) / max(max_score, 1), 4),
                "popularity",
            )
            for r in rows
        ]

    def _blend_recommendations(
        self,
        cf_recs: List[RecommendedItem],
        cbf_recs: List[RecommendedItem],
        limit: int,
    ) -> List[RecommendedItem]:
        """Merge CF and CBF scores with weighted blend."""
        scores: dict[str, dict] = {}

        if cf_recs:
            max_cf = max(r.score for r in cf_recs) or 1
            for r in cf_recs:
                scores[r.product_id] = {
                    "cf": r.score / max_cf,
                    "cbf": 0.0,
                    "reason": "collaborative",
                }

        if cbf_recs:
            max_cbf = max(r.score for r in cbf_recs) or 1
            for r in cbf_recs:
                if r.product_id not in scores:
                    scores[r.product_id] = {
                        "cf": 0.0,
                        "cbf": 0.0,
                        "reason": "content_based",
                    }
                scores[r.product_id]["cbf"] = r.score / max_cbf
                if scores[r.product_id]["cf"] > 0:
                    scores[r.product_id]["reason"] = "hybrid"

        blended = [
            RecommendedItem(
                pid,
                round(CF_WEIGHT * v["cf"] + CBF_WEIGHT * v["cbf"], 4),
                v["reason"],
            )
            for pid, v in scores.items()
        ]
        blended.sort(key=lambda x: x.score, reverse=True)
        return blended[:limit]
