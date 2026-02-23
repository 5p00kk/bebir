IMAGE_NAME := bebir
CONTAINER_NAME := bebir-dev

build:
	docker build -t $(IMAGE_NAME) .devcontainer/

run:
	docker run -it --rm \
		--name $(CONTAINER_NAME) \
		-v $(PWD):/workspace \
		-w /workspace \
		-v $(HOME)/.claude:/root/.claude \
		$(IMAGE_NAME) bash --login

stop:
	docker stop $(CONTAINER_NAME)

shell:
	docker exec -it $(CONTAINER_NAME) bash

.PHONY: build run stop shell
