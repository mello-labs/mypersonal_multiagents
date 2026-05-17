from fastapi import FastAPI

app = FastAPI(title="NEO Multiagents Kernel OS")


@app.get("/")
def read_root():
    """Root endpoint for the NEO Multiagents Kernel OS."""
    return {"message": "NEO Multiagents OS Kernel — Active"}


@app.get("/health")
def health_check():
    """Health check for the NEO Multiagents Kernel OS."""
    return {"status": "ok"}
