from django.db import migrations

REVIEWERS = "Reviewers"


def forward(apps, schema_editor):
    apps.get_model("auth", "Group").objects.get_or_create(name=REVIEWERS)
    # Questions imported before their history was kept get its first entry now.
    Question = apps.get_model("assessments", "Question")
    Event = apps.get_model("assessments", "QuestionEvent")
    Event.objects.bulk_create(
        Event(question=q, action="imported", to_status=q.status, note="History begins here: imported before Phase 6.")
        for q in Question.objects.filter(events__isnull=True))


def backward(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name=REVIEWERS).delete()


class Migration(migrations.Migration):
    """The question reviewers (decision 8): who may approve or send back a question in
    the review queue, and who is told when the item statistics flag one."""

    dependencies = [("assessments", "0003_history_and_review"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(forward, backward)]
