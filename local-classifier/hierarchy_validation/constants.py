from pydantic import BaseModel, Field
from typing import List


GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"
HIERARCHY_VALIDATION_LOGS = "/app/hierarchy_validation_logs.logs"


class ClassHierarchy(BaseModel):
    class_name: str = Field(..., alias="class")
    subclasses: list

class HierarchyCheckRequest(BaseModel):
    modelId:int
    classHierarchies: list
    
class FolderHierarchyRequest(BaseModel):
    modelId:int

class FlattenedFolderHierarchy(BaseModel):
    hierarchy:list
    modelId:int
    
class CorrectedFolderRequest(BaseModel):
    folderId:str
    modelId:int

