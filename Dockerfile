FROM klleon:base

COPY main.py .

EXPOSE 8000

CMD uvicorn main:app
