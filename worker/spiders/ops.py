from worker import app


@app.task
def clean_and_import(data):
    """Cleans, validates, and imports product data from a spider."""

    # Check for required fields
    required = ['vendor', 'sku']

    for field in required:
        assert field in data

    print(f'FAKE IMPORT: {data["vendor"]} {data["sku"]}')
