# Backend

## 환경 요구사항

- **Python 버전**: 3.12.1
- **패키지 관리**: Poetry

## 설치 및 실행

### 1. Poetry를 통한 의존성 설치

```bash
# Poetry가 설치되어 있지 않은 경우 먼저 설치
curl -sSL https://install.python-poetry.org | python3 -

# 또는 pip를 통한 설치
pip3 install poetry

# 프로젝트 의존성 설치 -> poetry.lock 파일의 의존성을 모두 install
poetry install
```

### 2. 가상환경 활성화

```bash
# Poetry 가상환경 활성화
poetry shell
# windows의 경우 powershell 사용 시 권한 문제가 있을 수 있으므로 아래의 명령어 사용
poetry env activate
```

### 3. Django 서버 실행

```bash
# 개발 서버 실행
python manage.py runserver

# 특정 포트로 실행
python manage.py runserver 8000
```
