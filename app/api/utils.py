from typing import Annotated

from fastapi import Depends, HTTPException
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt, ExpiredSignatureError
from datetime import datetime, timedelta

from starlette import status

from app.api.consts import ACCESS_TOKEN_EXPIRE, REFRESH_TOKEN_EXPIRE, JWT_SECRET_KEY, ALGORITHM, JWT_REFRESH_SECRET_KEY
from app.api.database import SessionLocal
from app.api.dtos import TokenResponse, TokenDetails
from app.api.enums import GrantType
from app.api.exceptions import CredentialsException
from app.api.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
db = SessionLocal()


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str):
    return pwd_context.verify(password, hashed_password)


def generate_token(user):
    access_token_expire_date = datetime.timestamp(datetime.now() + timedelta(seconds=ACCESS_TOKEN_EXPIRE))
    access_token_claims = {"exp": access_token_expire_date, "username": user.username, "id": user.id,
                           "token_type": "ACCESS_TOKEN"}
    access_token = jwt.encode(access_token_claims, JWT_SECRET_KEY, ALGORITHM)

    refresh_token_expire_date = datetime.timestamp(datetime.now() + timedelta(seconds=REFRESH_TOKEN_EXPIRE))
    refresh_token_claims = {"exp": refresh_token_expire_date, "username": user.username, "id": user.id,
                            "token_type": GrantType.REFRESH_TOKEN.value}
    refresh_token = jwt.encode(refresh_token_claims, JWT_REFRESH_SECRET_KEY, ALGORITHM)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=ACCESS_TOKEN_EXPIRE)


def validate_token_and_get_token_details(token):
    try:
        payload = jwt.decode(token, JWT_REFRESH_SECRET_KEY, ALGORITHM)
        username: str = payload.get("username")
        user_id: int = payload.get("id")
        token_type: str = payload.get("token_type")
        return TokenDetails(username=username, user_id=user_id, token_type=token_type)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise CredentialsException("Could not validate credentials")


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=ALGORITHM)
        username: str = payload.get("username")
        if username is None:
            raise credentials_exception
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user
