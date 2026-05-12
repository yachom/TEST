"""LLM 관련 자산 분리 — 프롬프트, 응답 스키마, 모델 단가.

이 패키지는 다음을 한 곳에 모은다:
  - prompts/  : 각 에이전트/서비스의 system+user 템플릿 + JSON 응답 스키마 (YAML)
  - pricing.yaml / pricing.py : 모델 토큰 단가 (USD per 1M tokens)
  - catalog.py : PromptCatalog — 키 기반 렌더링 + 버전 해시

호출 코드는 인라인 prompt 문자열을 들고 다니지 않고
PromptCatalog.render("exploration.planner", tools="...", address="...") 형태로 받는다.

별도 레포(fnpricing-llm) 로 추출할 때를 대비해 의존성을 core 안에서만 닫음:
  - core.llm 는 core.shared.infra.llm_client (LLMRequest) 만 의존
  - core.llm 외부는 PromptCatalog 인터페이스로만 접근
"""
