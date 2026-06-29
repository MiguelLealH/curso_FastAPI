import os
from datetime import datetime
from fastapi import FastAPI, Query, Body, HTTPException, Path
from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional, List, Union, Literal
from math import ceil
from sqlalchemy import create_engine, Integer,String,Text, DateTime
from sqlalchemy.orm import sessionmaker,Session,DeclarativeBase,Mapped,mapped_column

DATABASE_URL = os.getenv("DATABASE_URL","sqlite:///./blog.db")
print("Conectado a: ",DATABASE_URL)

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

# Creamos conexión a la BD 
# 1 DATABASE_URL
# 2 echo=True mostrar el SQL ejecutado en la terminal
# 3 future=True Indica que se utilizara la sintaxis reciente de SQLAlchemy
# 4 **engine_kwargs Es decesario para sqlite
engine = create_engine(DATABASE_URL,echo=True, future=True,**engine_kwargs)

# Creación de la sesion a la BD por cada request
# autoflush no envia cambios hasta hacer el commit, es decir evitar el autoguardado
SessionLocal = sessionmaker(bind=engine,autoflush=False,autocommit=False,class_=Session)

class Base(DeclarativeBase):
    pass

# Calse para representar una tabla
class PostORM(Base):
    # Nombre de la tabla
    __tablename__ = "posts"
    # Agregar atributos a la tabla
    # Mapped -> propiedad | mapped_column -> Definir los detalles del atributo
    id: Mapped[int] = mapped_column(Integer,primary_key=True,index=True)
    title: Mapped[str] = mapped_column(String(100),nullable=False,index=True)
    content: Mapped[str] = mapped_column(Text,nullable=False)
    create_at: Mapped[datetime] = mapped_column(
        DateTime,default=datetime.utcnow)

# create_all permite crear las tablas en caso de que no existan Solo para el ambiente de dev
Base.metadata.create_all(bind=engine) 

# Funcion para crear la sesion para cada que se entre a un endpoint

def get_db():
    # Creamos la sesion
    db = SessionLocal()
    try:
        # Probamos y enviamos la BD , FastAPI inyecta DB a la funcion que depende de esta sesión
        yield db
    finally:
        # Cuando finaliza la pausa del yield cierra la sesión 
        db.close()

app = FastAPI(title="Mini Blog")

BLOG_POST =[
    {"id":1, "title":"Hola desde FastAPI","content":"Mi primer post con FastAPI"},
    {"id":2, "title":"Mi segundo Post con FastAPI","content":"Mi segundo post con FastAPI"},
    {"id":3, "title":"Django vs FastAPI","content":"FastAPI es más rápido que Django por varias razones",
     "tags": [
         {"name": "Python"},
         {"name": "fastapi"},
         {"name": "DJANGO"},
         ]},
    {"id":4, "title":"Hola desde FastAPI","content":"Mi primer post con FastAPI"},
    {"id":5, "title":"Mi segundo Post con FastAPI","content":"Mi segundo post con FastAPI"},
    {"id":6, "title":"Django vs FastAPI","content":"FastAPI es más rápido que Django por varias razones"},
    {"id":7, "title":"Hola desde FastAPI","content":"Mi primer post con FastAPI"},
    {"id":8, "title":"Mi segundo Post con FastAPI","content":"Mi segundo post con FastAPI",
     "tags": [
         {"name": "Python"},
         {"name": "fastapi"},
         {"name": "DJANGO"},
         ]},
    {"id":9, "title":"Django vs FastAPI","content":"FastAPI es más rápido que Django por varias razones"},
    {"id":10, "title":"Hola desde FastAPI","content":"Mi primer post con FastAPI"},
    {"id":11, "title":"Mi segundo Post con FastAPI","content":"Mi segundo post con FastAPI"},
    {"id":12, "title":"Django vs FastAPI","content":"FastAPI es más rápido que Django por varias razones"},
    {"id":13, "title":"Hola desde FastAPI","content":"Mi primer post con FastAPI",
     "tags": [
         {"name": "Python"},
         {"name": "fastapi"},
         {"name": "DJANGO"},
         ]},
    {"id":14, "title":"Mi segundo Post con FastAPI","content":"Mi segundo post con FastAPI"},
    {"id":15, "title":"Django vs FastAPI","content":"FastAPI es más rápido que Django por varias razones"}
]

#Cuando heredamos nuestras clases con la clase BaseModel tipifica los datos para que sean ingresados de esa manera obligatoriamente

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
    
class PaginatedPost(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_prev: bool
    has_next: bool
    order_by: Literal["id","title"]
    direction: Literal["asc","desc"]
    search: Optional[str] = None
    items: List[PostPublic]

#endpoint get para home

@app.get("/") #Accede a la ruta raiz
def home():
    return {"message": "Bienvenidos a mi Mini Blog por Miguel Leal!"}

#endopoint get para obtener todos los post

# Utilizando Response Model
@app.get("/posts", response_model=PaginatedPost)
def list_posts(
    text: Optional[str] = Query(
    default=None,
    deprecated=True,
    description="Parametro obsoleto, usa 'query o search' en su lugar",
    ),
    query: Optional[str] = Query(
    default=None, # EL None del Query significa opcional
    description="Texto para buscar por título",
    alias="search", # A nivel publico se ve search pero a nivel codigo es query
    min_length=3,
    max_length=50,
    pattern=r"^[\w\sáéíóúÁÉÍÓÚüÜ]+$"
    #pattern=r"^[a-zA-Z]+$" #Solo letras
    ),
    #Paginación limit, offset, order_by y direction
    # Primero limitamos
    per_page: int = Query(
        10, # Valor por default
        ge=1,# Valor minimo
        le=50, # Valor Maximo
        description="Número de resultados (1-50)"
    ),
    # Desde donde vamos a comenzar
    page: int = Query(
        1,
        ge=1,
        description="Numero de página (>=1)"
    ),
    #Ordenación 
    order_by: Literal["id","title"] = Query( # Literal limitas a los valores que esten en la lista
        "id", description="Campo de orden"
    ),
    direction: Literal["asc","desc"] = Query(
        "asc", description="Dirección de orden"
    ) 
    ): 
    
    results = BLOG_POST
    
    #Para el ejercicio igualamos los valores pero no es la forma correcta para el deprecated
    query = query or text
    
    #Agregar filtro
    if query:
        results = [post for post in results if query.lower() in post["title"].lower()]
    
    # Ordenamos la lista conforme a la clave de comparación Literal["id","title"]
    # post:post[order_by] clave de comparación
    results = sorted(results, key=lambda post:post[order_by], reverse=(direction == "desc")) 
    
    #Obtenemos el total de posts
    total = len(results)
    
    #Obtenemos el numero total de paginas
    total_pages = ceil(total/per_page) if total > 0 else 0
    
    if total_pages == 0:
        current_page = 1
        items=[]
    else:
        current_page = min(page, total_pages)
        start = (current_page -1) * per_page
        items = results[start: start + per_page] #[inico:fin]
    
    has_prev = current_page > 1
    has_next = current_page < total_pages if total_pages > 0 else False
    
    return PaginatedPost(
        page = current_page,
        per_page = per_page, 
        total = total,
        total_pages = total_pages,
        has_prev = has_prev,
        has_next = has_next,
        order_by = order_by,
        direction = direction,
        search = query,
        items=items
    )

#endpoint para hacer busqueda dentro de las tags
@app.get("/posts/by-tags", response_model=List[PostPublic])
def filter_by_tag(
    tags: List[str] = Query(
        ...,
        min_length= 2,
        description= "Una o mas etiquetas. Ejemplo: ?tags=python&tags=fastapi"
    )
):
    tags_lower = [tag.lower() for tag in tags]
    return [
        #iterar sobre post
        post for post in BLOG_POST if any(tag["name"].lower() for tag in post.get("tags",[]))
    ]


#endpoint para obtener un post especifico y filtrar content
# Con Response model

# Union da la facilidad de evaluar ambos modelos  primero OPostPublic  y en caso de que no tenga contenido evalua el segundo 
#Path ayuda a agregar metadata, validaciones y reglas en los parametros
@app.get("/posts/{post_id}",response_model=Union[PostPublic,PostSummary], response_description="Post encontrado")
def get_post(post_id: int = Path(
    ...,
    #Agregamos primer condicion
    #ge grader  or equal mayor o igual que
    #gt grader than mayor
    #le less or equal
    #lt less
    ge=1,
    title="ID del post",
    description="Identificador entero del post. Debe ser mayor a 1",
    example=1
    ), include_content: bool = Query(default=True, description="Incluir o no el contenido")):
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