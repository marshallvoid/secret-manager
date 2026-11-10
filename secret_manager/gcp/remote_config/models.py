from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

VALUE_TYPES: list[str] = ["STRING", "BOOLEAN", "NUMBER", "JSON"]
COLOR_HEX: dict[str, str] = {
    "BLUE": "#8ab4f8",
    "BROWN": "#bcaaa4",
    "CYAN": "#78d9ec",
    "DEEP_ORANGE": "#fcad70",
    "GREEN": "#81c995",
    "INDIGO": "#9fa8da",
    "LIME": "#d4e157",
    "ORANGE": "#fdd663",
    "PINK": "#ff8bcb",
    "PURPLE": "#c58af9",
    "TEAL": "#4ecde6",
}
TAG_COLORS: list[str] = list(COLOR_HEX)
KEY_RE = re.compile(pattern=r"[A-Za-z_][A-Za-z0-9_]*")


# Mirrors the REST API; unknown fields are kept so a write sends them back unchanged
class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def to_api(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class ParamValue(ApiModel):
    value: str | None = None
    use_in_app_default: bool | None = Field(default=None, alias="useInAppDefault")

    # personalization and rollout values: kept as they are, not edited here
    def is_raw(self) -> bool:
        return self.value is None and not self.use_in_app_default

    def describe(self) -> str:
        if self.is_raw():
            return "(" + ", ".join(self.model_extra or {}) + ")"

        if self.use_in_app_default:
            return "(use in-app default)"

        return self.value if self.value else '""'


class ApiParameter(ApiModel):
    default_value: ParamValue | None = Field(default=None, alias="defaultValue")
    conditional_values: dict[str, ParamValue] = Field(default_factory=dict, alias="conditionalValues")
    description: str = ""
    value_type: str = Field(default="STRING", alias="valueType")


class ApiGroup(ApiModel):
    description: str = ""
    parameters: dict[str, ApiParameter] = Field(default_factory=dict)


class Condition(ApiModel):
    name: str
    expression: str
    tag_color: str = Field(default="", alias="tagColor")

    def to_api(self) -> dict[str, Any]:
        data = super().to_api()

        if not self.tag_color:
            data.pop("tagColor", None)

        return data


class UpdateUser(ApiModel):
    email: str = ""


class TemplateVersion(ApiModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow", coerce_numbers_to_str=True)

    version_number: str = Field(default="", alias="versionNumber")
    update_time: str = Field(default="", alias="updateTime")
    update_user: UpdateUser = Field(default_factory=UpdateUser, alias="updateUser")
    update_origin: str = Field(default="", alias="updateOrigin")
    update_type: str = Field(default="", alias="updateType")
    description: str = ""


class ApiTemplate(ApiModel):
    conditions: list[Condition] = Field(default_factory=list)
    parameters: dict[str, ApiParameter] = Field(default_factory=dict)
    parameter_groups: dict[str, ApiGroup] = Field(default_factory=dict, alias="parameterGroups")
    version: TemplateVersion | None = None


class VersionList(ApiModel):
    versions: list[TemplateVersion] = Field(default_factory=list)


class ApiError(ApiModel):
    message: str = ""


class ErrorBody(ApiModel):
    error: ApiError = Field(default_factory=ApiError)


# A parameter as the app edits it: groups are a field here, not a level of nesting
class Parameter(BaseModel):
    key: str
    value_type: str = "STRING"
    description: str = ""
    group: str = ""
    default: ParamValue | None = None
    conditional: dict[str, ParamValue] = Field(default_factory=dict)

    @classmethod
    def from_api(cls, key: str, data: ApiParameter, group: str) -> Parameter:
        return cls(
            key=key,
            value_type=data.value_type,
            description=data.description,
            group=group,
            default=data.default_value,
            conditional=dict(data.conditional_values),
        )

    def to_api(self) -> dict[str, Any]:
        data: dict[str, Any] = {"valueType": self.value_type}

        if self.default is not None:
            data["defaultValue"] = self.default.to_api()

        if self.conditional:
            data["conditionalValues"] = {name: value.to_api() for name, value in self.conditional.items()}

        if self.description:
            data["description"] = self.description

        return data


class Template(BaseModel):
    etag: str
    conditions: list[Condition] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    # group name → description
    groups: dict[str, str] = Field(default_factory=dict)
    version: TemplateVersion | None = None

    def condition_names(self) -> list[str]:
        return [condition.name for condition in self.conditions]

    def parameter(self, key: str) -> Parameter | None:
        return next((param for param in self.parameters if param.key == key), None)

    def body(self) -> dict[str, Any]:
        ungrouped = {param.key: param.to_api() for param in self.parameters if not param.group}
        groups: dict[str, Any] = {}

        for name, description in self.groups.items():
            members = {param.key: param.to_api() for param in self.parameters if param.group == name}

            # the API refuses empty groups
            if not members:
                continue

            groups[name] = {"parameters": members}

            if description:
                groups[name]["description"] = description

        return {
            "conditions": [condition.to_api() for condition in self.conditions],
            "parameters": ungrouped,
            "parameterGroups": groups,
        }

    def rename_condition(self, old: str, new: str) -> None:
        for param in self.parameters:
            if old in param.conditional:
                param.conditional = {(new if name == old else name): value for name, value in param.conditional.items()}

    def drop_condition(self, name: str) -> None:
        self.conditions = [condition for condition in self.conditions if condition.name != name]

        for param in self.parameters:
            param.conditional.pop(name, None)


def parse_template(api: ApiTemplate, etag: str) -> Template:
    template = Template(etag=etag, conditions=list(api.conditions), version=api.version)

    for key, param in api.parameters.items():
        template.parameters.append(Parameter.from_api(key=key, data=param, group=""))

    for group, group_data in api.parameter_groups.items():
        template.groups[group] = group_data.description

        for key, param in group_data.parameters.items():
            template.parameters.append(Parameter.from_api(key=key, data=param, group=group))

    template.parameters.sort(key=lambda param: param.key.lower())

    return template


def check_key(key: str) -> str | None:
    if not KEY_RE.fullmatch(key):
        return "Keys use letters, digits and _, and do not start with a digit."

    if len(key) > 256:
        return "Keys are at most 256 characters."

    return None


def check_value(value_type: str, value: str) -> str | None:
    if value_type == "BOOLEAN" and value not in ("true", "false"):
        return "A boolean value is true or false."

    if value_type == "NUMBER":
        try:
            float(value)
        except ValueError:
            return f"'{value}' is not a number."

    if value_type == "JSON":
        try:
            json.loads(s=value)
        except ValueError as exc:
            return f"Invalid JSON: {exc}"

    return None
