run:
	streamlit run app/main.py

test:
	pytest -q

fmt:
	.venv/bin/black app tests || echo "Black not installed. Run: pip install black"
