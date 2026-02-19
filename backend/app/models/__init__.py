# import every model here so sqlalchemy knows about all the tables.
# alembic looks at this to figure out what needs to be created in the database.
from app.models.users import User
from app.models.channels import Channel
from app.models.videos import Video
from app.models.stats import VideoStats, VideoAnalytics
from app.models.ml import VideoEmbedding, Cluster, ClusterMembership, Prediction
from app.models.alerts import Alert

__all__ = [
    "User",
    "Channel",
    "Video",
    "VideoStats",
    "VideoAnalytics",
    "VideoEmbedding",
    "Cluster",
    "ClusterMembership",
    "Prediction",
    "Alert",
]
