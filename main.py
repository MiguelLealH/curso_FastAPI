import os
from datetime import datetime
from fastapi import FastAPI, Query, Body, HTTPException, Path,status,Depends
from pydantic import BaseModel, Field, field_validator, EmailStr, ConfigDict
from typing import Optional, List, Union, Literal
from math import ceil
from sqlalchemy import create_engine, Integer,String,Text, DateTime,select,func, UniqueConstraint,ForeignKey,Table,Column
from sqlalchemy.orm import sessionmaker,Session,DeclarativeBase,Mapped,mapped_column, relationship, selectinload, joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

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

# Creamos Tabla intermedia para la relación n:n entre posts y tags
post_tags = Table(
    "post_tags", # Nombre de la tabla
    Base.metadata,
    # Enlazar con los valores que iran dentro de la tabla, es decir las columnas que tendrá esta tabla
    Column("post_id", # Nombre de la columna
           ForeignKey("posts.id",ondelete="CASCADE"), # Foreign Key
           primary_key=True),
    Column("tag_id", # Nombre de la columna
           ForeignKey("tags.id",ondelete="CASCADE"), # Foreign Key
           primary_key=True)     
)


# Clase para crear la tabla authors
class AuthorORM(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(Integer,primary_key=True,index=True)
    name: Mapped[str] = mapped_column(String(100),nullable=False)
    email: Mapped[str] = mapped_column(String(100),unique=True,index=True)
    
    # Generamos la relación entre tabla posts y autors 1:n
    # posts: relación ORM que conecta cada autor con la lista de sus posts (objetos PostORM).
    posts: Mapped[List["PostORM"]] = relationship(
        back_populates="author")

# Clase para la tabla etiquetas
class TagORM(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(Integer,primary_key=True,index=True)
    name: Mapped[str] = mapped_column(String(100),unique=True,index=True)
    
    # Generamos la relación entre tabla posts y tags n:n
    posts: Mapped[List["PostORM"]] = relationship(
        secondary=post_tags,
        back_populates="tags")
     
# Clase para representar una tabla del tipo post
class PostORM(Base):
    # Nombre de la tabla
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("title",name="unique_post_title"),)
    # Agregar atributos a la tabla
    # Mapped -> propiedad | mapped_column -> Definir los detalles del atributo
    id: Mapped[int] = mapped_column(Integer,primary_key=True,index=True)
    title: Mapped[str] = mapped_column(String(100),nullable=False,index=True)
    content: Mapped[str] = mapped_column(Text,nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,default=datetime.utcnow)
    
    # Creamos Foreign Key
    # Optional[int] → puede ser un número entero o None.
    # author_id: columna en la tabla posts que guarda el ID del autor (clave foránea).
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("authors.id"))
   
    # Crear un atributo de relación de tabla posts con authors
    # Optional["AuthorORM"] → puede contener un objeto AuthorORM o None.
    # author: relación ORM que conecta cada post con su autor (objeto AuthorORM).
    author: Mapped[Optional["AuthorORM"]] = relationship(
        back_populates="posts")
    
    tags: Mapped[List["TagORM"]] = relationship(
        secondary=post_tags, # Uso y llamada de la tabla intermedia post_tags
        back_populates="posts",
        lazy="selectin", # Busqueda la realizara con selectin
        passive_deletes=True) # Respetar el ondelete en cascada

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

# Cuando heredamos nuestras clases con la clase BaseModel tipifica los datos para que sean ingresados de esa manera obligatoriamente

class Tag(BaseModel):
    name: str = Field(...,min_length=2,max_length=30,description="Nombre de la etiqueta")
    
    model_config = ConfigDict(from_attributes=True)
    
class Author(BaseModel):
    name: str = Field(
        default="Anónimo",
        min_length=10,
        description="Mínimo 10 caracteres para le nombre del autor",
        examples=["Sor Juana Inés de la cruz"]
    ) 
    
    email: EmailStr
    
    model_config = ConfigDict(from_attributes=True)

class PostBase(BaseModel):
    title: str
    content: str
    tags: Optional[List[Tag]] = Field(default_factory=list) #[] por cada objeto que se cree ene l programa
    author: Optional[Author] = None
    
    model_config = ConfigDict(from_attributes=True)

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
    @classmethod # Se va a utilizar a la clase completa ayuda a minpular los valores a nivel de clase
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
    # Esta configuracion sirve para que Pydentic entienda que recibe objeto de SQLAlchemist y lo convierta a JSON 
    model_config = ConfigDict(from_attributes=True)
    
class PostSummary(BaseModel):
    id: int
    title: str
    # Para aceptar objetos, tambien se validan postsumary a partir de un objeto
    model_config = ConfigDict(from_attributes=True)
    
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
    ),
    db: Session = Depends(get_db) 
    ): 
    
    results = select(PostORM)
    
    #Para el ejercicio igualamos los valores pero no es la forma correcta para el deprecated
    query = query or text
    
    #Agregar filtro
    if query:
        #  ilike es una variante de LIKE que hace la comparación sin importar mayúsculas o minúsculas.
        results = results.where(PostORM.title.ilike(f"%{query}%"))
    
    # Ordenamos la consulta
    order_col  = PostORM.id if order_by == "id" else func.lower(PostORM.title)
    results = results.order_by(
        order_col.asc() if direction=="asc" else order_col.desc())
    
    #Obtenemos el total de posts
    total = db.scalar(select(func.count()).select_from(results.subquery())) or 0
    
    #Obtenemos el numero total de paginas
    total_pages = ceil(total/per_page) if total > 0 else 0
    
    if total_pages == 0:
        current_page = 1
        items: List[PostORM] = []
    else:
        current_page = min(page, total_pages)
        start = (current_page -1) * per_page
        # 1.- results.limit(5).offset(5) → genera la consulta SQL equivalente a SELECT * FROM posts LIMIT 5 OFFSET 5;:
        # 2.- db.execute(...) → ejecuta esa consulta en la base de datos.
        # 3.- .scalars() → extrae los objetos ORM (cada fila convertida en instancia de PostORM).
        # 4.- .all() → devuelve una lista con esos objetos Ejemplo:.
        """
        [
            PostORM(id=6, title="Validación de datos"),
            PostORM(id=7, title="Async en FastAPI"),
            PostORM(id=8, title="Seguridad con JWT"),
            PostORM(id=9, title="Deploy en Docker"),
            PostORM(id=10, title="Testing con Pytest")
        ]
        """ 
        items = db.execute(results.limit(
            per_page).offset(start)).scalars().all()
    
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
        min_length= 1,
        description= "Una o mas etiquetas. Ejemplo: ?tags=python&tags=fastapi"
    ),
    db: Session = Depends(get_db)
):
    # Normalizar las etiquetas recibidas --Limpia espacios y convierte a minúsculas.
    normalized_tag_names = [tag.strip().lower() for tag in tags if tag.strip().lower()]
    
    if not normalized_tag_names:
        return []
    
    post_list = (
        select(PostORM).options( # .options() se usa para configurar cómo se cargan las relaciones cuando haces una consulta.
            selectinload(PostORM.tags), #  carga los tags asociados en una consulta adicional optimizada n:n
            joinedload(PostORM.author), #  carga el autor en la misma consulta con un JOIN
        ).where( #Filtra posts que tengan al menos un tag cuyo nombre esté en la lista normalizada.
            PostORM.tags.any(func.lower(TagORM.name).in_(normalized_tag_names)) # comparación insensible a mayúsculas.
        ).order_by(PostORM.id.asc())
    )
    
    # .scalars() → devuelve objetos PostORM.
    # .all() → lista de resultados.
    posts = db.execute(post_list).scalars().all()
    
    return posts


#endpoint para obtener un post especifico y filtrar content
# Con Response model

# Union da la facilidad de evaluar ambos modelos  primero OPostPublic  y en caso de que no tenga contenido evalua el segundo 
#Path ayuda a agregar metadata, validaciones y reglas en los parametros
@app.get("/posts/{post_id}",response_model=Union[PostPublic,PostSummary],
         response_description="Post encontrado")
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
    ), include_content: bool = Query(default=True, description="Incluir o no el contenido"),db:Session=Depends(get_db)):
    
    #Buscar el post_id dentro del modelo y lo almacena en post
    # Creamos la consulta SQL que selecciona todos los campos del modelo PostORM y Añade una condición a la consulta: solo traer el registro cuyo id sea igual a post_id
    # SELECT * FROM posts WHERE id = <post_id>;
    post_find = select(PostORM).where(PostORM.id == post_id)
    # Ejecuta la consulta en la base de datos usando la sesión db.
    # .scalar_one_or_none() Si encuentra exactamente un registro → devuelve ese objeto PostORM.
    post = db.execute(post_find).scalar_one_or_none()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")
    
    if include_content:
        # .model_validate(post, ...) Su función es validar y convertir los datos que le pasas (post) para que cumplan con el esquema definido en PostPublic.
        # from_attributes=True Indica que Pydantic debe construir el modelo a partir de atributos de un objeto, no solo de un diccionario.
        return PostPublic.model_validate(post, from_attributes=True)
    
    return PostSummary.model_validate(post,from_attributes=True)

# Método Post Crea

@app.post("/posts", response_model=PostPublic, response_description="Post creado (OK)", status_code=status.HTTP_201_CREATED)
def create_post(post: PostCreate, db: Session = Depends(get_db)): 
    author_obj = None
    # post.author sale del atributo author de la clase PostORM
    if post.author:
        author_obj = db.execute(
            select(AuthorORM).where(AuthorORM.email == post.author.email)
        ).scalar_one_or_none()
        
        # Creamos el author sino existe en la BD
        if not author_obj:
            author_obj = AuthorORM(
                name=post.author.name,
                email=post.author.email)
            
            db.add(author_obj)  
            db.flush() # para asegurar que genere un id en AutorsORM antes de usarlo en Post
    
    new_post = PostORM(title=post.title,content=post.content,author=author_obj)
    
    # post.tags sale del atributo tags de la clase PostORM
    for tag in post.tags:
        tag_obj = db.execute(
            select(TagORM).where(TagORM.name.ilike(tag.name))
        ).scalar_one_or_none()
        
        if not tag_obj:
            tag_obj = TagORM(name=tag.name)
            db.add(tag_obj)
            db.flush()
        
        # Agregamos la etiqueta a la tabla intermedia
        # Aqui se hace la relación muchos a muchos
        # 1.- SQLAlchemy no inserta directamente en la tabla tags, sino que:
        # 2.- Registra en memoria que este PostORM debe estar relacionado con ese TagORM.
        # 3.- Cuando se hace db.commit(), SQLAlchemy inserta una fila en la tabla intermedia post_tags con los IDs correspondientes:
        # INSERT INTO post_tags (post_id, tag_id) VALUES (<id del post>, <id del tag>);
        new_post.tags.append(tag_obj)
    
    try:
        # 1 Marcar la insercion
        db.add(new_post)
        # 2 Confirmar la inserción con un commit
        db.commit()
        # 3 Traer los valores finales como el id y el created_at
        db.refresh(new_post)
        return new_post
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El título ya existe, prueba con otro")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500,detail="Error al crear el post")


# PUT Actualiza

@app.put("/posts/{post_id}",response_model=PostPublic,response_description="Post actualizado",response_model_exclude_none=True)
def update_post(post_id: int, data: PostUpdate, db: Session = Depends(get_db)):
    #Buscar el post_id dentro del modelo y lo almacena en post
    post = db.get(PostORM,post_id)
    
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")
    
    # Se transforma el objeto en una lista de tuplas  [("title","Hola"),("content","Contenido")] con items()
    playload = data.model_dump(exclude_unset=True).items() 
    
    try:
        # Actualizamos solo los campos enviados
        for field, value in playload:
            setattr(post,field,value)
            
        db.add(post)
        db.commit()
        db.refresh(post)
        return PostPublic.model_validate(post, from_attributes=True)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500,detail="Error al actualizar el post")
        
# DELETE

@app.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT) # 204 Salio bien pero no regresaremos contenido
def delete_post(post_id: int, db: Session = Depends(get_db)):
    #Buscar el post_id dentro del modelo y lo almacena en post
    post = db.get(PostORM,post_id)
    
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")
    
    try:
        # Eliminamos el elemento
        db.delete(post)
        db.commit()
        return
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500,detail="Error al eliminar el post")