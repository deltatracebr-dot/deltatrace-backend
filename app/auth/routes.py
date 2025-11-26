from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from .schemas import UserLogin
from ..common.security import create_access_token

router = APIRouter()

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # TODO: validar usuário real
    if form_data.username != "admin@deltatrace.local" or form_data.password != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas"
        )

    access_token = create_access_token(subject=form_data.username)
    return {"access_token": access_token, "token_type": "bearer"}
