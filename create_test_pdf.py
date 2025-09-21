#!/usr/bin/env python3

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Create a simple test PDF that our parser will fail on (expected behavior)
# but will test the upload flow
def create_test_pdf():
    pdf_file = "test_statement.pdf"
    c = canvas.Canvas(pdf_file, pagesize=letter)

    # Add some basic content
    c.drawString(100, 750, "TEST BANK STATEMENT")
    c.drawString(100, 700, "Account Number: 1234567890")
    c.drawString(100, 650, "Date: 2025-01-01")

    # Add a simple transaction-like line
    c.drawString(100, 600, "2025-01-01    UPI Transfer    100.00    5000.00")

    c.save()
    print(f"Created {pdf_file}")

if __name__ == "__main__":
    create_test_pdf()