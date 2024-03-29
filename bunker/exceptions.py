from bunker import schemas

class NotFoundError(Exception):
    """Raised when a requested entity does not exist"""
    pass

class AlreadyExistsError(Exception):
    """Raised when attempting to create a row or relation which
    already exists."""

class AdminNotAssociatedError(Exception):
    """Raised when attempting to transfer ownership to
    an admin not part of the community"""
    def __init__(self, admin: schemas.Admin, community: schemas.Community, *args):
        self.admin = admin
        self.community = community
        super().__init__(*args)

class AdminOwnsCommunityError(Exception):
    """Raised when attempting to remove an owner from a
    community"""
    def __init__(self, admin: schemas.Admin, *args):
        self.admin = admin
        super().__init__(*args)

class TooManyAdminsError(Exception):
    """Raised when attempting to exceed the upper limit of
    admins each community is allowed to have"""
    def __init__(self, *args):
        super().__init__(*args)


class IntegrationFailureError(Exception):
    """Generic exception raised when an integration fails to
    perform a remote action."""

class IntegrationValidationError(IntegrationFailureError):
    """Exception raised when an integration fails to validate"""

class IntegrationBanError(IntegrationFailureError):
    """Exception raised when an integration fails to ban or
    unban a player."""
    def __init__(self, player_id: str, *args: object) -> None:
        self.player_id = player_id
        super().__init__(*args)

class IntegrationBulkBanError(IntegrationFailureError):
    """Exception raised when an integration fails to ban or
    unban one or more players during a bulk operation."""
    def __init__(self, player_ids: list[str], *args: object) -> None:
        self.player_ids = player_ids
        super().__init__(*args)

class AlreadyBannedError(IntegrationFailureError):
    """Raised when a player is already banned"""
    def __init__(self, player_id: str, *args: object) -> None:
        self.player_id = player_id
        super().__init__(*args)
