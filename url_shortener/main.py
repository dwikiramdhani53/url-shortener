from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
import validators
from sqlalchemy.orm import Session
from starlette.datastructures import URL

from . import schemas, models, crud
from .database import SessionLocal, engine
from .config import get_settings

app = FastAPI()
models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def raise_bad_request(message):
    raise HTTPException(status_code=400, detail=message)

def raise_not_found(request):
    message = f"URL '{request.url}' doesn't exist"
    raise HTTPException(status_code=404, detail=message)

def get_admin_info(db_url: models.URL) -> schemas.URLInfo:
    base_url = URL(get_settings().base_url)
    admin_endpoint = app.url_path_for("administration info", secret_key=db_url.secret_key)
    db_url.url = str(base_url.replace(path=db_url.key))
    db_url.admin_url = str(base_url.replace(path=admin_endpoint))
    return db_url

@app.get("/")
def read_root():
    return "Welcome to URL Shortener API"

@app.post("/url", response_model=schemas.URLInfo)
def create_url(url: schemas.URLBase, db: Session = Depends(get_db)):
    if not validators.url(url.target_url):
        raise_bad_request(message="Your provided URL is not valid")

    db_url = crud.create_db_url(db, url)
    return get_admin_info(db_url)

@app.post("/url/custom", response_model=schemas.URLInfo, name="Create shorten URL with custom key")
def create_url_custom_key(url: schemas.URLCustom, db: Session = Depends(get_db)):
    if not validators.url(url.target_url):
        raise_bad_request(message="Your provided URL is not valid")
    if crud.get_db_url_by_key(db, url.key):
        raise_bad_request(message="Key already used, please use another key")

    db_url = crud.create_custom_db_url(db, url)
    return get_admin_info(db_url)
    

@app.get("/{url_key}")
def forward_to_target_url(
        url_key: str,
        request: Request,
        db: Session = Depends(get_db)
    ):
    if db_url := crud.get_db_url_by_key(db, url_key):
        crud.update_db_clicks(db, db_url)
        return RedirectResponse(db_url.target_url)
    else:
        raise_not_found(request)

@app.get(
    "/admin/{secret_key}",
    name="administration info",
    response_model=schemas.URLInfo,
)
def get_url_info(secret_key: str, request: Request, db: Session = Depends(get_db)):
    if db_url := crud.get_db_url_by_secret_key(db, secret_key):
        return get_admin_info(db_url)
    else:
        raise_not_found(request)

@app.delete("/admin/{secret_key}")
def deactive_url(secret_key: str, request: Request, db: Session = Depends(get_db)):
    if db_url := crud.deactive_db_url_by_secret_key(db, secret_key):
        message = f"Successfully deactive shortened URL for '{db_url.target_url}'"
        return {"detail": message}
    else:
        raise_not_found(request)