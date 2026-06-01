"""
CORS middleware configuration.
"""

from fastapi.middleware.cors import CORSMiddleware


def setup_cors(app, origins: list = None):
    """Add CORS middleware to the app."""
    if origins is None:
        origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
            "https://predict.previlium.com",
            "https://app.predict.previlium.com",
            "https://predict-pp.com",
            "https://www.predict-pp.com",
        ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
