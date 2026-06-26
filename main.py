from fastapi import FastAPI, Query, Body, HTTPException
from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional, List, Union

app = FastAPI(title="Mini Blog")

BLOG_POST =[
    {"id":1, "title":"Hola desde FastAPI","content":"Mi primer post con FastAPI"},
    {"id":2, "title":"Mi segundo Post con FastAPI","content":"Mi segundo post con FastAPI"},
    {"id":3, "title":"Django vs FastAPI","content":"FastAPI es más rápido que Django por varias razones"}
]

class Tag(BaseModel):
    name: str = Field(...,min_length=2,max_length=30,description="Nombre de la etiqueta")
    

class Author(BaseModel):
    name: str = Field(
        default="Anónimo",
        min_length=10,
        description="Mínimo 10 caracteres para le nombre del autor",
        examples=["Sor Juana Inés de la cruz"]
    ) 
    
    email: EmailStr

class PostBase(BaseModel):
    title: str
    content: str
    tags: Optional[List[Tag]] = Field(default_factory=list) #[] por cada objeto que se cree ene l programa
    author: Optional[Author] = None

class PostCreate(BaseModel):
    title: str = Field(
        #Campo obligatorio
        ...,
        min_length = 3,
        max_length= 100,
        description= "Título del post mínimo 3 caracteres y máximo 100",
        examples=["Mi primer post con FastAPI"]
    )
    content:Optional[str] = Field(
        default="Sin contenido.",
        min_length=10,
        description="Mínimo 10 caracteres",
        examples=["Este es un contenido válido por que tiene 10 caracteres o más"]
    )
    tags: List[Tag] = Field(default_factory=list) # Enlazamos Tag con PostCreate
    author: Optional[Author] = None
    
    
    @field_validator("title") # Evalua el campo title
    @classmethod # Se va a utilizar a la clase completa ayuda a minpular los valores a nivle de clase
    def not_allowed_title(cls,value:str) -> str: # -> return
        forbiden_words = ["spam","pinche","puto","pendejo","porno","puta","pendeja"]
        for fw in forbiden_words: 
            if fw in value.lower():
                raise ValueError(f"El título no puede contener la palabra: '{fw}'")
        return value

class PostUpdate(BaseModel):
    title: Optional[str] = Field(None,min_length=3,max_length=100)
    content: Optional[str] = None # Hacemos el campo opcional con un valor por defecto None


# Response Model
# Definimos el molde de la respuesta

class PostPublic(PostBase):
    id: int
    #title: str Se hereda de PostBase
    #content: str Se hereda de PostBase
    
class PostSummary(BaseModel):
    id: int
    title: str
    


#endpoint get para home

@app.get("/") #Accede a la ruta raiz
def home():
    return {"message": "Bienvenidos a mi Mini Blog por Miguel Leal!"}

#endopoint get para obtener todos los post

# Utilizando Response Model
@app.get("/posts", response_model=List[PostPublic])
def list_posts(query: str | None = Query(default=None, description="Texto para buscar por título")):
    #Agregar filtro
    if query:
        results = [post for post in BLOG_POST if query.lower() in post["title"].lower()]
        return results
    
    return BLOG_POST

#endpoint para obtener un post especifico y filtrar content
# Con Response model

# Union da la facilidad de evaluar ambos modelos  primero OPostPublic  y en caso de que no tenga contenido evalua el segundo 
@app.get("/posts/{post_id}",response_model=Union[PostPublic,PostSummary], response_description="Post encontrado")
def get_post(post_id: int, include_content: bool = Query(default=True, description="Incluir o no el contenido")):
    for post in BLOG_POST:
        if post["id"] == post_id:
            if not include_content:
                return {"id": post["id"],"title": post["title"]}
            return post
        
    return HTTPException(status_code=404, detail="Post no encontrado")


# Método Post Crea

@app.post("/posts", response_model=PostPublic, response_description="Post creado")
def create_post(post: PostCreate): 
    new_id = (BLOG_POST[-1]["id"] + 1) if BLOG_POST else 1
    
    new_post = {"id": new_id, 
                "title": post.title,
                "content": post.content, 
                "tags":[tag.model_dump() for tag in post.tags],
                "author": post.author.model_dump() if post.author else None
                }
    BLOG_POST.append(new_post)
    return new_post


# PUT Actualiza

@app.put("/posts/{post_id}",response_model=PostPublic,response_description="Post actualizado",response_model_exclude_none=True)
def update_post(post_id: int, data: PostUpdate):
    for post in BLOG_POST:
        if post["id"] == post_id:
            playload = data.model_dump(exclude_unset=True) # Se transforma el objeto en diccionario  {"title": "Hola"}
            if "title" in playload: 
                post["title"] = playload["title"]
                if "content" in playload:
                    post["content"] = playload["content"]
                return post
    raise HTTPException(status_code=404, detail="Post no encontrado")



# DELETE

@app.delete("/posts/{post_id}", status_code=204) # 204 Salio bien pero no regresaremos contenido
def delete_post(post_id: int):
    for index, post in enumerate(BLOG_POST):
        if post["id"] == post_id:
            BLOG_POST.pop(index)
            return
    raise HTTPException(status_code=404,detail="Post no encontrado.")