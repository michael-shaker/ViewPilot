# import every model here so sqlalchemy knows about all the tables.
# alembic looks at this to figure out what needs to be created in the database.
from app.models.alerts import Alert
from app.models.channels import Channel
from app.models.ml import Cluster, ClusterMembership, Prediction, VideoEmbedding
from app.models.stats import VideoAnalytics, VideoStats
from app.models.users import User
from app.models.videos import Video

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
