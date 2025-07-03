from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv



# Import routes
from routes import users, restaurant_chains, restaurant_outlets, subscriptions,menu_management,table_management,billing,order_management,notifications

# Import database and middleware
from utils.database import engine, Base, get_db

# Load environment variables
load_dotenv()

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title="Restaurant Management System API",
    description="A scalable backend for restaurant management POS system",
    version="1.0.0",
    openapi_tags=[
        {"name": "users", "description": "User management operations"},
        {"name": "restaurant-chains", "description": "Restaurant chain management"},
        {"name": "restaurant-outlets", "description": "Restaurant outlet management"},
        {"name": "subscriptions", "description": "Subscription management"}
    ],
    swagger_ui_parameters={
        "persistAuthorization": True,
        "defaultModelsExpandDepth": -1
    }
)


# Configure CORS and Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(users.router)
app.include_router(restaurant_chains.router)
app.include_router(restaurant_outlets.router)
app.include_router(subscriptions.router)
app.include_router(menu_management.router)
app.include_router(table_management.router)
app.include_router(billing.router)
app.include_router(order_management.router) 
app.include_router(notifications.router)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Restaurant Management System API"}

# Main run block
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
