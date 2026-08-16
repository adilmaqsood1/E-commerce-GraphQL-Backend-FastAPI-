# E-Commerce GraphQL Backend

> **FastAPI** + **Strawberry GraphQL** + **PostgreSQL** + **Redis** + **AI Recommendations**

A production-grade e-commerce backend demonstrating advanced GraphQL patterns, clean architecture, and AI-powered product recommendations.

---

## 🏗 Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.111 |
| GraphQL | Strawberry GraphQL |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Cache | Redis 7 |
| Auth | JWT (access + refresh) + RBAC |
| Background Jobs | ARQ (asyncio Redis queue) |
| AI Recommendations | SVD Collaborative Filtering + sentence-transformers CBF |
| Testing | Pytest + pytest-asyncio |
| Containerisation | Docker + Docker Compose |

---

## 🚀 Quick Start

### 1. Clone and configure
```bash
git clone <repo-url>
cd E-commerce-GraphQL-Backend-FastAPI-
cp .env.example .env
# Edit .env with your secrets
```

### 2. Start services with Docker Compose
```bash
docker-compose up -d postgres redis
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run migrations
```bash
alembic upgrade head
```

### 5. Start the API
```bash
uvicorn app.main:app --reload
```

### 6. Open GraphiQL
Visit **http://localhost:8000/graphql** to explore the API interactively.

---

## 📁 Project Structure

```
app/
├── core/           # Config, DB, Redis, Security, Permissions, Context
├── models/         # SQLAlchemy ORM models
├── schemas/        # Strawberry GraphQL types
├── resolvers/      # Query / Mutation / Subscription resolvers
├── dataloaders/    # DataLoaders (N+1 prevention)
├── services/       # Business logic
└── workers/        # ARQ background jobs

alembic/            # Database migrations
tests/              # Pytest test suite
```

---

## 🔎 Example Queries

### Product with full details
```graphql
query {
  product(id: "prod_123") {
    id
    name
    price
    category { name }
    brand { name }
    images { url }
    variants { id name price stock }
    reviews { rating comment }
    inventory { available isLowStock }
  }
}
```

### Paginated product list with filters
```graphql
query {
  products(
    filters: { categoryId: "electronics", minPrice: 100, inStock: true }
    sort: RATING
    first: 20
    after: "cursor_xyz"
  ) {
    totalCount
    pageInfo { hasNextPage endCursor }
    edges {
      cursor
      node { id name price averageRating }
    }
  }
}
```

### AI-powered recommendations
```graphql
query {
  recommendedProducts(limit: 10) {
    score
    reason   # "collaborative" | "content_based" | "hybrid" | "popularity"
    product {
      id name price
      images { url }
    }
  }
}
```

### My orders
```graphql
query {
  myOrders {
    id orderNumber status total createdAt
    items {
      quantity unitPrice
      product { name images { url } }
    }
    payment { status method }
    shippingAddress { city country }
  }
}
```

### Add to cart
```graphql
mutation {
  addToCart(input: { productId: "prod_123", quantity: 2 }) {
    id quantity unitPrice totalPrice
  }
}
```

### Checkout
```graphql
mutation {
  createOrder(input: {
    addressId: "addr_123"
    paymentMethod: "CARD"
    couponCode: "SAVE10"
  }) {
    id orderNumber status total
  }
}
```

### Subscribe to order status
```graphql
subscription {
  orderStatusChanged(orderId: "order_123") {
    orderId
    status
    updatedAt
  }
}
```

---

## 🔐 Authentication

```
POST /graphql → register mutation → returns { accessToken, refreshToken }
All protected queries → Authorization: Bearer <accessToken>
```

**Roles:**
- `CUSTOMER` — view products, manage cart, create orders, write reviews
- `SELLER` — + create/manage products, manage inventory, view seller orders
- `ADMIN` — + manage users, manage coupons, view analytics

---

## 🤖 AI Recommendation System

The recommendation engine uses a **hybrid** approach:

1. **Collaborative Filtering (60%)** — SVD matrix factorisation on user-item interaction matrix
2. **Content-Based (40%)** — `all-MiniLM-L6-v2` sentence embeddings + cosine similarity
3. **Cold-start fallback** — Popularity score (sold_count × 0.7 + rating × 0.3) for new users
4. **Redis caching** — Results cached for 1 hour per user

Interactions tracked: `view (1.0)`, `wishlist (2.0)`, `cart (2.0)`, `review (3.0)`, `purchase (5.0)`

---

## 🧪 Running Tests

```bash
pytest tests/ -v --asyncio-mode=auto
```

---

## 🐳 Full Docker Setup

```bash
docker-compose up --build
```

This starts: PostgreSQL, Redis, FastAPI app (with auto-migrations), and ARQ worker.

---

## ✨ GraphQL Concepts Demonstrated

| Concept | Implementation |
|---|---|
| DataLoader (N+1 fix) | CategoryLoader, UserLoader, ProductLoader |
| Cursor Pagination | Relay-style `Connection/Edge/PageInfo` |
| Filtering + Sorting | `ProductFilterInput` + `ProductSortField` enum |
| Nested queries | Product → Category → Brand → Variants → Reviews → User |
| Mutations | 20+ mutations covering all business operations |
| Subscriptions | WebSocket order status + inventory via Redis pub/sub |
| RBAC | Role-based decorators on all protected resolvers |
