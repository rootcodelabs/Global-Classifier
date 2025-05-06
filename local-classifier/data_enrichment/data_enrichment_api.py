from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from data_enrichment import DataEnrichment
from typing import List, Optional

app = FastAPI()
data_enrichment = DataEnrichment()

class ParaphraseRequest(BaseModel):
    text: str
    num_return_sequences: Optional[int] = 1
    language_id: Optional[str] = None

class ParaphraseResponse(BaseModel):
    paraphrases: List[str]

@app.post("/paraphrase", response_model=ParaphraseResponse)
def paraphrase(request: ParaphraseRequest):
    try:
        paraphrases = data_enrichment.enrich_data(
            request.text, 
            request.num_return_sequences, 
            request.language_id
        )
        if not paraphrases:
            raise HTTPException(status_code=400, detail="Unsupported language or other error")
        return ParaphraseResponse(paraphrases=paraphrases)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
