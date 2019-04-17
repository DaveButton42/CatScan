from pathlib import Path

from jacowvalidator.tables import check_table_titles

test_dir = Path(__file__).parent / 'data'


def test_tables():
    from docx import Document
    doc = Document(test_dir / 'jacow_template_a4.docx')

    # hard code known issues with this doc for the moment
    type_of_checks = ['order_ok', 'style_ok']
    issues = {
        1: [],
        2: ['style_ok'],
        3: ['used', 'order_ok'],
    }

    table_titles = check_table_titles(doc)
    assert len(table_titles) == 3

    for item in table_titles:
        # TODO optimise this
        if 'used' in issues[item['id']]:
            assert item['used'] == 0, f"{item['id']} used check passes but it should fail"
        else:
            assert item['used'] > 0, f"{item['id']} used check failed"

        for check in type_of_checks:
            if check in issues[item['id']]:
                assert item[check] is False, f"{item['id']} {check} check passes but it should fail"
            else:
                assert item[check], f"{item['id']} {check} check failed"
