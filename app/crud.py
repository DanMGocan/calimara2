"""Compatibility facade for split repository modules.

New backend code should import from `app.repositories.<domain>` or from a domain
repository package. Existing routers and tests can keep using `app.crud`.
"""

from .repositories.users import *
from .repositories.posts import *
from .repositories.writing import *
from .repositories.audio import *
from .repositories.jobs import *
from .repositories.comments import *
from .repositories.mentions import *
from .repositories.profile import *
from .repositories.referrals import *
from .repositories.economy import *
from .repositories.forum import *
from .repositories.messages import *
from .repositories.notifications import *
from .repositories.friends import *
from .repositories.follows import *
from .repositories.moderation import *
from .repositories.reports import *
from .repositories.series import *
from .repositories.reactions import *
from .repositories.premium import *
from .repositories.clubs import *
from .repositories.theatre import *
from .repositories.stafeta import *
