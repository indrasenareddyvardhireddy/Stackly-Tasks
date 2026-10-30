from fastapi import Query


class Pagination:
    def __init__(self, skip: int = Query(0, ge=0, description="Records to skip"),
                 limit: int = Query(10, ge=1, le=100, description="Max records to return")):
        self.skip = skip
        self.limit = limit


def paginate_response(items, total, page: Pagination):
    return {"total": total, "skip": page.skip, "limit": page.limit, "items": items}
