"""Seed a fictional shop so the demo works on first run. Edit or delete it in the admin."""
from django.db import migrations

ARTICLES = [
    ("Opening hours and location", "Alpine Trail Bikes is at 14 Lindenweg, Interlaken. The shop and workshop are open Tuesday to Friday from 9:00 to 18:30 and Saturday from 9:00 to 16:00. We are closed on Sundays, Mondays and Swiss public holidays."),
    ("Shipping and delivery", "We ship within Switzerland and to the EU. Accessories and parts ship in 1 to 2 working days. Complete bikes are assembled and checked first, so they ship within 5 working days. Shipping is free for orders over 150 CHF. Below that it costs 9 CHF within Switzerland and 19 CHF to the EU. Complete bikes cost a flat 49 CHF to ship. You get a tracking link by email when the parcel leaves."),
    ("Returns and refunds", "You can return unused items within 30 days of delivery for a full refund. Bikes that have been ridden can be returned within 14 days for store credit, as long as they have no damage. Start a return by emailing the order number to returns@alpinetrailbikes.example. Refunds reach your original payment method within 7 working days after we receive the item. Return shipping is paid by the customer unless the item arrived faulty."),
    ("Warranty", "Every new bike comes with a 5 year warranty on the frame and 2 years on components. E-bike batteries and motors are covered for 2 years or 500 charge cycles, whichever comes first. The warranty does not cover normal wear such as tyres, brake pads and chains, or damage from crashes. Keep your receipt, as we need the order number for any warranty claim."),
    ("Choosing the right frame size", "As a guide: height 155 to 165 cm takes size S, 165 to 175 cm size M, 175 to 185 cm size L, and 185 to 195 cm size XL. If you are between two sizes, choose the smaller frame for a more agile ride or the larger for more stability. We are happy to check your size in the shop, which takes about ten minutes."),
    ("Workshop and bike service", "Our workshop services all brands. A basic service costs 79 CHF and includes brake and gear adjustment, a safety check and chain lubrication. A full service costs 189 CHF and adds a drivetrain clean, wheel truing and a brake bleed. Parts are charged separately. Typical turnaround is 3 working days, and a first service within 3 months of buying a bike from us is free. Book by phone or in the shop."),
    ("Test rides", "You can test ride any bike we have in stock, free of charge, for up to one hour. Bring a photo ID. For e-bikes we recommend booking a slot in advance, especially on Saturdays. Test rides are not available in heavy rain or snow."),
    ("Payment methods", "We accept Visa, Mastercard, TWINT, PayPal and bank transfer online, and cash and all major cards in the shop. For bikes over 2,000 CHF you can pay in 12 monthly instalments at 0 percent interest through our financing partner. The instalment option is shown at checkout."),
    ("E-bike battery care and range", "Our e-bikes have a range of 60 to 120 km per charge, depending on the model, the support level and the terrain. A full charge takes about 4.5 hours. To keep the battery healthy, store it indoors between 10 and 20 degrees Celsius and at 40 to 70 percent charge if you will not ride for more than a month. Do not leave it on the charger for days."),
    ("Bike rental", "We rent mountain bikes and e-bikes from April to October. A mountain bike costs 55 CHF per day and an e-mountain bike 85 CHF per day, helmet included. Rentals of three days or more get 15 percent off. A deposit by credit card is required. We do not rent bikes in winter."),
    ("Contacting the team", "The fastest way to reach a person is the shop phone, +41 33 555 01 42, during opening hours. You can also email hello@alpinetrailbikes.example and we reply within one working day. For questions about an existing order, have your order number ready."),
]


def seed(apps, schema_editor):
    Site = apps.get_model("chat", "Site")
    Article = apps.get_model("chat", "Article")
    site, created = Site.objects.get_or_create(
        slug="demo",
        defaults={
            "name": "Alpine Trail Bikes",
            "greeting": "Hi! I can answer questions about our bikes, delivery, returns and the workshop.",
            "accent": "#ff7a59",
            "allowed_origins": "*",
        },
    )
    if created:
        Article.objects.bulk_create(Article(site=site, title=title, body=body) for title, body in ARTICLES)


def unseed(apps, schema_editor):
    apps.get_model("chat", "Site").objects.filter(slug="demo").delete()


class Migration(migrations.Migration):
    dependencies = [("chat", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
