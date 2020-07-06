from dataclasses import dataclass


# necessary environment variables for scripts
@dataclass
class Config:
    mongo_connection_string: str = ''
