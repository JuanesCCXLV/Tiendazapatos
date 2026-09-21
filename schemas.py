from pydantic import BaseModel, EmailStr

class ClienteCreate(BaseModel):
 nombre: str
 email: EmailStr
 telefono: str


class ClienteResponse(BaseModel):
 id: int 
 nombre: str 
 email: EmailStr
 telefono: str

 class Config:
  from_attributes = True 
  
