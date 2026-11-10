from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app


def _make_test_png_bytes() -> bytes:
    img = Image.new("RGB", (800, 600), color=(220, 38, 38))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_full_catalog_and_recognition_flow():
    with TestClient(app) as client:
        # 1. 健康检查
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "healthy"

        # 2. 获取分类树
        cats_res = client.get("/api/v1/categories")
        assert cats_res.status_code == 200
        cats = cats_res.json()["data"]["items"]
        assert len(cats) >= 7

        # 3. 获取品牌列表与奔驰品牌详情
        brands_res = client.get("/api/v1/brands")
        assert brands_res.status_code == 200
        brands = brands_res.json()["data"]["items"]
        mb = next(b for b in brands if b["name_zh"] == "奔驰")
        mb_detail = client.get(f"/api/v1/brands/{mb['id']}").json()["data"]
        assert any(s["name_zh"] == "E级" for s in mb_detail["series_list"])

        # 4. 拍照识车：命中已有宝马 3系
        png_bytes = _make_test_png_bytes()
        rec_matched = client.post(
            "/api/v1/recognition",
            files={"image": ("bmw_3.png", png_bytes, "image/png")},
            data={"client_request_id": "test_req_bmw_001"},
        )
        assert rec_matched.status_code == 200
        assert rec_matched.json()["data"]["status"] == "matched"
        assert "宝马" in rec_matched.json()["data"]["vehicle"]["brand_name"]

        # 5. 拍照识车：仅识别到奔驰 E 级车系，不下推具体配置
        rec_series = client.post(
            "/api/v1/recognition",
            files={"image": ("mb_e级.png", png_bytes, "image/png")},
            data={"client_request_id": "test_req_mbe_002", "hint_keyword": "e级"},
        )
        assert rec_series.status_code == 200
        assert rec_series.json()["data"]["status"] == "matched"
        assert rec_series.json()["data"]["match_level"] == "series"

        # 6. 拍照识车：未收录新车型自动进入 pending_review
        rec_pending = client.post(
            "/api/v1/recognition",
            files={"image": ("xiaomi_su7.png", png_bytes, "image/png")},
            data={"client_request_id": "test_req_su7_003", "hint_keyword": "su7"},
        )
        assert rec_pending.status_code == 200
        assert rec_pending.json()["data"]["status"] == "pending_review"

