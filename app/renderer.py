from jinja2 import Environment, BaseLoader
from weasyprint import HTML

from app.models import Invoice


_TEMPLATE = """
<!doctype html>
<html lang="de">
<head>
    <meta charset="utf-8" />
    <title>Rechnung {{ invoice.number }}</title>
    <style>
        body { font-family: Arial, sans-serif; color: #222; }
        .header { display: flex; justify-content: space-between; }
        .address { margin-top: 16px; }
        table { width: 100%; border-collapse: collapse; margin-top: 24px; }
        th, td { border-bottom: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f5f5f5; }
        .totals { margin-top: 16px; width: 40%; margin-left: auto; }
        .totals td { border: none; padding: 4px 8px; }
        .notes { margin-top: 24px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h2>{{ invoice.issuer.name }}</h2>
            <div>{{ invoice.issuer.street }}</div>
            <div>{{ invoice.issuer.postal_code }} {{ invoice.issuer.city }}</div>
            {% if invoice.issuer.country %}<div>{{ invoice.issuer.country }}</div>{% endif %}
            {% if invoice.issuer.email %}<div>{{ invoice.issuer.email }}</div>{% endif %}
        </div>
        <div>
            <div><strong>Rechnung Nr.</strong> {{ invoice.number }}</div>
            <div><strong>Datum:</strong> {{ invoice.date }}</div>
            <div><strong>Fällig:</strong> {{ invoice.due_date }}</div>
        </div>
    </div>

    <div class="address">
        <strong>Rechnung an:</strong>
        <div>{{ invoice.recipient.name }}</div>
        <div>{{ invoice.recipient.street }}</div>
        <div>{{ invoice.recipient.postal_code }} {{ invoice.recipient.city }}</div>
        {% if invoice.recipient.country %}<div>{{ invoice.recipient.country }}</div>{% endif %}
        {% if invoice.recipient.email %}<div>{{ invoice.recipient.email }}</div>{% endif %}
    </div>

    <table>
        <thead>
            <tr>
                <th>Beschreibung</th>
                <th>Menge</th>
                <th>Einzelpreis</th>
                <th>Gesamt</th>
            </tr>
        </thead>
        <tbody>
            {% for item in invoice.line_items %}
            <tr>
                <td>{{ item.description }}</td>
                <td>{{ "%.2f" | format(item.quantity) }}</td>
                <td>{{ "%.2f" | format(item.unit_price) }} {{ invoice.currency }}</td>
                <td>{{ "%.2f" | format(item.total) }} {{ invoice.currency }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <table class="totals">
        <tr>
            <td>Zwischensumme</td>
            <td>{{ "%.2f" | format(invoice.subtotal) }} {{ invoice.currency }}</td>
        </tr>
        <tr>
            <td>Steuern ({{ "%.0f" | format(invoice.tax_rate * 100) }}%)</td>
            <td>{{ "%.2f" | format(invoice.tax_amount) }} {{ invoice.currency }}</td>
        </tr>
        <tr>
            <td><strong>Gesamt</strong></td>
            <td><strong>{{ "%.2f" | format(invoice.total) }} {{ invoice.currency }}</strong></td>
        </tr>
    </table>

    {% if invoice.notes %}
    <div class="notes">
        <strong>Hinweise</strong>
        <div>{{ invoice.notes }}</div>
    </div>
    {% endif %}
</body>
</html>
"""


def generate_html(invoice: Invoice) -> str:
    env = Environment(loader=BaseLoader(), autoescape=True)
    template = env.from_string(_TEMPLATE)
    return template.render(invoice=invoice)


def to_pdf(html_content: str) -> bytes:
    return HTML(string=html_content).write_pdf()


def to_png(html_content: str) -> bytes:
    return HTML(string=html_content).write_png()
