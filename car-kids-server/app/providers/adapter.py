from typing import Optional

from app.core.config import settings


class VehicleRecognitionProvider:
    """第三方汽车图像识别适配器基类（遵循需求文档 7.2 规范）。"""

    async def recognize(
        self,
        image_bytes: bytes,
        mime_type: str,
        hint_keyword: Optional[str] = None,
    ) -> dict:
        """返回标准化的识别候选结构，不直接返回面向儿童的最终知识文案。"""
        raise NotImplementedError


class ConfigurableVehicleRecognitionProvider(VehicleRecognitionProvider):
    """
    可配置第三方识别适配器：
    - 当配置了真实的 RECOGNITION_API_BASE_URL 与 RECOGNITION_API_KEY 时，通过异步 HTTP 调用远端识车服务；
    - 在本地开发/联调阶段，支持根据传入的测试提示词或默认识别返回标准化的品牌/车系/具体车型候选。
    """

    async def recognize(
        self,
        image_bytes: bytes,
        mime_type: str,
        hint_keyword: Optional[str] = None,
    ) -> dict:
        if (
            settings.RECOGNITION_API_BASE_URL
            and settings.RECOGNITION_API_KEY
            and settings.RECOGNITION_API_KEY != "replace_me"
            and "example.com" not in settings.RECOGNITION_API_BASE_URL
        ):
            import httpx

            async with httpx.AsyncClient(
                timeout=settings.RECOGNITION_TIMEOUT_SECONDS
            ) as client:
                resp = await client.post(
                    settings.RECOGNITION_API_BASE_URL,
                    headers={"Authorization": f"Bearer {settings.RECOGNITION_API_KEY}"},
                    files={"image": ("upload.jpg", image_bytes, mime_type)},
                )
                resp.raise_for_status()
                payload = resp.json()
                return {
                    "provider": settings.RECOGNITION_PROVIDER,
                    "candidates": payload.get("candidates", []),
                }

        hint = (hint_keyword or "").strip().lower()
        if "unrecognized" in hint or "unknown" in hint:
            return {
                "provider": settings.RECOGNITION_PROVIDER,
                "candidates": [
                    {
                        "brand_name": None,
                        "brand_name_zh": None,
                        "product_line_name": None,
                        "series_name": None,
                        "series_name_zh": None,
                        "model_name": None,
                        "trim_name": None,
                        "model_year": None,
                        "vehicle_category": "汽车",
                        "confidence": 0.32,
                    }
                ],
            }

        if "e级" in hint or "e-class" in hint:
            # 演示车系级识别（只识别到奔驰 E 级，未确认具体年款/配置）
            return {
                "provider": settings.RECOGNITION_PROVIDER,
                "candidates": [
                    {
                        "brand_name": "Mercedes-Benz",
                        "brand_name_zh": "奔驰",
                        "product_line_name": None,
                        "series_name": "E-Class",
                        "series_name_zh": "E 级",
                        "model_name": None,
                        "trim_name": None,
                        "model_year": None,
                        "vehicle_category": "轿车",
                        "confidence": 0.88,
                    }
                ],
            }

        if "new" in hint or "pending" in hint or "su7" in hint:
            # 演示本地未收录车系/车型的自动待审核入库
            return {
                "provider": settings.RECOGNITION_PROVIDER,
                "candidates": [
                    {
                        "brand_name": "Xiaomi",
                        "brand_name_zh": "小米汽车",
                        "product_line_name": None,
                        "series_name": "SU7",
                        "series_name_zh": "SU7",
                        "model_name": "Xiaomi SU7 Max",
                        "trim_name": "四驱超长续航高阶智驾版",
                        "model_year": 2024,
                        "vehicle_category": "轿车",
                        "confidence": 0.91,
                    }
                ],
            }

        # 默认返回设计稿上排第3张图示例：宝马 3系 (BMW 325Li)
        return {
            "provider": settings.RECOGNITION_PROVIDER,
            "candidates": [
                {
                    "brand_name": "BMW",
                    "brand_name_zh": "宝马",
                    "product_line_name": None,
                    "series_name": "3 Series",
                    "series_name_zh": "3系",
                    "model_name": "BMW 325Li",
                    "trim_name": "325Li M运动套装",
                    "model_year": 2024,
                    "vehicle_category": "轿车",
                    "confidence": 0.93,
                }
            ],
        }


def get_recognition_provider() -> VehicleRecognitionProvider:
    return ConfigurableVehicleRecognitionProvider()

