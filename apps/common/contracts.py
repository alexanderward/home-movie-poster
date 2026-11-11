from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

RequiredText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)
]
RequiredName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]


class ContractModel(BaseModel):
    """Validated, immutable application contracts, including Django attribute reads."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        from_attributes=True,
        populate_by_name=True,
    )
