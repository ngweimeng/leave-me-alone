run:
	streamlit run app/main.py

test:
	pytest -q

fmt:
	black app tests
