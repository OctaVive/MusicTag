from django.db import models


class Album(models.Model):
    key = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=1024)
    album_artist = models.CharField(max_length=1024, blank=True, db_index=True)
    year = models.CharField(max_length=10, blank=True)
    genre = models.CharField(max_length=1024, blank=True)
    label = models.CharField(max_length=1024, blank=True)
    catalog_number = models.CharField(max_length=1024, blank=True)
    track_count = models.PositiveIntegerField(default=0)
    disc_count = models.PositiveIntegerField(default=1)
    duration = models.FloatField(default=0)
    cover_hash = models.CharField(max_length=64, blank=True)
    cover_track_id = models.BigIntegerField(null=True)
    issue_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["album_artist", "title"]


class Track(models.Model):
    path = models.TextField(unique=True)
    filename = models.CharField(max_length=1024)
    folder = models.TextField(db_index=True, blank=True)
    format = models.CharField(max_length=8, db_index=True)
    size = models.BigIntegerField(default=0)
    mtime = models.BigIntegerField(default=0)
    indexed_at = models.DateTimeField(auto_now=True)
    duration = models.FloatField(default=0)
    bitrate = models.IntegerField(default=0)
    sample_rate = models.IntegerField(default=0)
    channels = models.IntegerField(default=0)
    title = models.CharField(max_length=1024, blank=True, db_index=True)
    artist = models.CharField(max_length=1024, blank=True, db_index=True)
    album = models.CharField(max_length=1024, blank=True, db_index=True)
    album_artist = models.CharField(max_length=1024, blank=True, db_index=True)
    genre = models.CharField(max_length=1024, blank=True, db_index=True)
    date = models.CharField(max_length=10, blank=True, db_index=True)
    track_no = models.IntegerField(default=0, db_index=True)
    disc_no = models.IntegerField(default=0)
    catalog_number = models.CharField(max_length=1024, blank=True, db_index=True)
    has_cover = models.BooleanField(default=False, db_index=True)
    cover_hash = models.CharField(max_length=64, blank=True)
    tags = models.JSONField(default=dict)
    issue_flags = models.JSONField(default=list)
    read_error = models.TextField(blank=True)
    album_group = models.ForeignKey(Album, null=True, on_delete=models.SET_NULL, related_name="tracks")

    class Meta:
        ordering = ["disc_no", "track_no", "path"]


class Operation(models.Model):
    kind = models.CharField(max_length=32)
    status = models.CharField(max_length=24, default="running")
    summary = models.TextField(blank=True)
    track_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["-id"]


class OperationEntry(models.Model):
    operation = models.ForeignKey(Operation, on_delete=models.CASCADE, related_name="entries")
    track = models.ForeignKey(Track, null=True, on_delete=models.SET_NULL)
    path = models.TextField()
    before_tags = models.JSONField(default=dict)
    after_tags = models.JSONField(default=dict)
    before_cover = models.CharField(max_length=64, blank=True)
    after_cover = models.CharField(max_length=64, blank=True)
    backup = models.TextField(blank=True)
    before_fingerprint = models.CharField(max_length=64, blank=True)
    after_fingerprint = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=24, default="pending")
    error = models.TextField(blank=True)


class Job(models.Model):
    kind = models.CharField(max_length=32)
    status = models.CharField(max_length=24, default="queued", db_index=True)
    total = models.IntegerField(default=0)
    done = models.IntegerField(default=0)
    succeeded = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    payload = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    cancel_requested = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)


class Preset(models.Model):
    name = models.CharField(max_length=100, unique=True)
    fields = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ParserPattern(models.Model):
    name = models.CharField(max_length=100, unique=True)
    template = models.CharField(max_length=500)
    builtin = models.BooleanField(default=False)


class AppSetting(models.Model):
    key = models.CharField(max_length=80, primary_key=True)
    value = models.JSONField()
