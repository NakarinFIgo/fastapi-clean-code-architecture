from app.domain.entities.crud import CrudResource, Datasource
from app.domain.models.user import UserModel, UserPermissionModel

# Add a CrudResource here to expose a model under /api/v1/data/<slug>/.
# This mirrors config.EntitiyModels in the Go project, minus UserTokenModel: the Go list
# endpoint hands every logged-in user all access/refresh tokens, so it is left out here.
CRUD_RESOURCES: list[CrudResource] = [
    CrudResource("users", Datasource.POSTGRESQL, UserModel, hidden=frozenset({"password"})),
    CrudResource(
        "user_permissions",
        Datasource.POSTGRESQL,
        UserPermissionModel,
        # Go's UserPermissionModel has no json tags on these fields.
        aliases={"id": "ID", "user_id": "UserId"},
    ),
]
