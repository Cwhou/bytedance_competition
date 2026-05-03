from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_ui_tars_desktop() -> Path:
    """cua-lark 与 UI-TARS-desktop 为兄弟目录时（如 feishu/ 工作区）自动定位。"""
    cua_root = Path(__file__).resolve().parents[2]
    return cua_root.parent / "UI-TARS-desktop"


def _sdk_dist_marker(root: Path) -> Path:
    return root / "packages" / "ui-tars" / "sdk" / "dist" / "index.mjs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    vlm_base_url: str = Field(default="https://ark.cn-beijing.volces.com/api/v3", alias="VLM_BASE_URL")
    vlm_api_key: str = Field(default="", alias="VLM_API_KEY")
    vlm_model: str = Field(default="doubao-seed-1-6-251015", alias="VLM_MODEL")

    ui_tars_desktop_root: Path = Field(default_factory=_default_ui_tars_desktop, alias="UI_TARS_DESKTOP_ROOT")

    @field_validator("ui_tars_desktop_root", mode="before")
    @classmethod
    def _ui_root_empty_means_default(cls, v: object) -> object:
        # .env 里写 UI_TARS_DESKTOP_ROOT= 空串时，pydantic 会覆盖默认 Path，常变成 cwd，导致去 cua-lark\packages\... 找 SDK
        if v is None:
            return _default_ui_tars_desktop()
        if isinstance(v, str) and not v.strip():
            return _default_ui_tars_desktop()
        return v

    @model_validator(mode="after")
    def _check_ui_tars_layout(self) -> Settings:
        root = self.ui_tars_desktop_root.expanduser().resolve()
        marker = _sdk_dist_marker(root)
        if not marker.is_file():
            raise ValueError(
                "UI_TARS_DESKTOP_ROOT 指向的目录下未找到 UI-TARS SDK 构建产物：\n"
                f"  期望文件: {marker}\n"
                "请确认：\n"
                "  1) 该变量为 **UI-TARS-desktop 仓库根目录**（含 packages/ui-tars 的目录），不是 cua-lark 目录；\n"
                "  2) 已在 UI-TARS-desktop 下执行过 pnpm install（生成 sdk/dist）；\n"
                "  3) 若不需要自定义路径，请从 .env 中 **删除** UI_TARS_DESKTOP_ROOT 这一行，或留空等价的「不要写 = 后面为空」——"
                "不要写 `UI_TARS_DESKTOP_ROOT=` 空值（已自动按兄弟目录推断时除外）。\n"
                f"  当前解析到的根目录: {root}"
            )
        return self

    def bridge_env(self) -> dict[str, str]:
        return {
            "VLM_BASE_URL": self.vlm_base_url,
            "VLM_API_KEY": self.vlm_api_key,
            "VLM_MODEL": self.vlm_model,
            "UI_TARS_DESKTOP_ROOT": str(self.ui_tars_desktop_root.resolve()),
        }
