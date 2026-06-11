from fastapi import HTTPException


def not_found(entity: str = "Resource") -> HTTPException:
    return HTTPException(status_code=404, detail=f"{entity} not found.")


def forbidden(detail: str = "You do not have permission to perform this action.") -> HTTPException:
    return HTTPException(status_code=403, detail=detail)


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=409, detail=detail)


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)
