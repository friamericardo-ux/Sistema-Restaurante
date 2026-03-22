from dataclasses import dataclass

@dataclass
class User:
    id: int
    username: str
    password_hash: str
    role: str = "admin"
    restaurante_id: int = None