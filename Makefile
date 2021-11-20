test-build:
	docker build . -f Dockerfile.test --tag=ctgrzr-test
test-run:
	docker run --rm ctgrzr-test
test-cleanup:
	docker rmi ctgrzr-test
test: test-build test-run test-cleanup

format:
	black ctgrzr/*
