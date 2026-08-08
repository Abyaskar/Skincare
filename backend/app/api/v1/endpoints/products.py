"""
GET /products, GET /products/{id}, POST /products/batch, GET /products/facets

WHY GET: these read without changing anything. Same request, same answer — so
they're cacheable, bookmarkable, shareable and safe for a crawler to re-fetch.
Filters live in query parameters precisely so those URLs ARE shareable:
/products?brand=cerave&max_price=20 is a link you can send someone.

STRATEGIC ROLE: this is the only endpoint with no AI in its path. It is the
degradation target — if FAISS fails to load or the LLM is down, the storefront
falls back to a filtered, paginated catalogue instead of an error page. Every
AI product should have a boring path that always works.

NOTE: the original codebase exposed this resource at BOTH /products/{id} and
/product/{id}. Two URLs for one resource splits caches, splits analytics and
confuses SEO. The singular route is kept as a permanent redirect for
compatibility and marked deprecated.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_product_repository
from app.repositories.product_repository import ProductRepository
from app.schemas.product import (
    FacetsResponse,
    ProductDetailResponse,
    ProductListResponse,
    ProductResponse,
)
from app.services.recommendation_service import doc_to_response
from app.utils.ingredient_intel import AVOID_GROUPS

router = APIRouter()


class BatchRequest(BaseModel):
    """POST /products/batch — fetch several products in one round-trip."""

    product_ids: list[str] = Field(..., min_length=1, max_length=20)


@router.get("/facets", response_model=FacetsResponse, summary="Filter options")
async def get_facets(
    repo: ProductRepository = Depends(get_product_repository),
) -> FacetsResponse:
    """
    Everything the guided flow needs to build its own controls.

    Without this the frontend hardcodes brand lists and price ranges, which rot
    silently the moment the catalogue changes. The UI should never know more
    about the data than the database does.
    """
    facets = await repo.get_facets()
    return FacetsResponse(
        brands=facets["brands"],
        product_types=facets["product_types"],
        price_min=facets["price_min"],
        price_max=facets["price_max"],
        avoid_groups=sorted(AVOID_GROUPS.keys()),
        concerns=facets["concerns"],
        total_products=facets["total"],
        products_with_known_price=facets["with_price"],
    )


@router.get("", response_model=ProductListResponse, summary="List products")
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    brand: str | None = Query(None),
    product_type: str | None = Query(None),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    sort: str = Query("name", pattern="^(name|price_asc|price_desc)$"),
    repo: ProductRepository = Depends(get_product_repository),
) -> ProductListResponse:
    """Paginated catalogue with deterministic filters. No AI in this path."""
    items, total = await repo.list_products(
        page=page,
        page_size=page_size,
        brand=brand,
        product_type=product_type,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
    )
    return ProductListResponse(
        items=[doc_to_response(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/batch", response_model=list[ProductResponse], summary="Fetch several products")
async def get_products_batch(
    request: BatchRequest,
    repo: ProductRepository = Depends(get_product_repository),
) -> list[ProductResponse]:
    """
    Used by the compare view. Three sequential round-trips is a visible delay
    on mobile; one call is not.
    """
    docs = await repo.find_by_ids(request.product_ids)
    order = {pid: i for i, pid in enumerate(request.product_ids)}
    docs.sort(key=lambda d: order.get(d.id or "", 999))
    return [doc_to_response(d) for d in docs]


@router.get("/{product_id}", response_model=ProductDetailResponse, summary="Get product by ID")
async def get_product_by_id(
    product_id: str,
    repo: ProductRepository = Depends(get_product_repository),
) -> ProductDetailResponse:
    """Retrieve a single product. The URL is the product's permanent address."""
    doc = await repo.find_by_id(product_id)
    return ProductDetailResponse(**doc_to_response(doc).model_dump(), metadata=doc.metadata)


# Deprecated singular alias, kept so existing links don't break.
product_detail_router = APIRouter()


@product_detail_router.get(
    "/{product_id}",
    response_model=ProductDetailResponse,
    summary="Get product by ID (deprecated alias)",
    deprecated=True,
)
async def get_product_deprecated(
    product_id: str,
    repo: ProductRepository = Depends(get_product_repository),
) -> ProductDetailResponse:
    """Deprecated: use GET /products/{id}. Kept only for backwards compatibility."""
    doc = await repo.find_by_id(product_id)
    return ProductDetailResponse(**doc_to_response(doc).model_dump(), metadata=doc.metadata)
