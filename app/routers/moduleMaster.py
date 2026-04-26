from app.models.subModuleMasterModel import SubModuleMaster
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..models.moduleMasterModel import ModuleMaster
from ..core.database import get_db



router = APIRouter(prefix="/module", tags=["module"])

@router.get("getModules/")
def get_all_modules(db: Session = Depends(get_db)):
    modules = db.query(ModuleMaster).all()
    return modules



@router.get("/getSubModules/")
def get_sub_modules(db : Session = Depends(get_db)):
    sub_modules = db.query(SubModuleMaster).all()
    return sub_modules

 
