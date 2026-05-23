# Streamlit 설정 파일 — GitHub 업로드용

GitHub 웹에서는 `.streamlit` 폴더를 드래그로 올리기 어렵습니다.
**아래 방법으로 GitHub에서 직접 만들어 주세요.**

## 방법 (Create new file)

1. GitHub 저장소 페이지 → **Add file** → **Create new file**
2. 파일 이름 입력란에 **아래 한 줄을 그대로** 붙여넣기:

```
.streamlit/config.toml
```

3. 아래 `[theme]` 내용 전체를 붙여넣기 (streamlit_config_copy.toml 과 동일)
4. **Commit changes** 클릭

> 주의: 파일 이름을 `streamlit/config.toml` 또는 `config.toml` 로만 올리면 **동작하지 않습니다.**  
> 반드시 **`.streamlit/config.toml`** 경로여야 합니다. (맨 앞 점 `.` 포함)

## 로컬 PC에 이미 있는 경우

경로: `ai-stock-dashboard\.streamlit\config.toml`

Windows 탐색기에서 **숨긴 항목** 표시를 켜야 `.streamlit` 폴더가 보입니다.
