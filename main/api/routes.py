from base64 import b64encode

from flask import Response, jsonify, request, url_for
from pydantic import ValidationError

from main import app, bp, log_buffer, services, socketio
from main.db import models, schemas
from main.tasks import process_urls_from_zip_archive
from main.utils.helpers import convert_to_serializable, make_int


@bp.route('/resources/', methods=['GET'])
def get_resources():
    # extract query params
    domain_zone = request.args.get('domain_zone')
    resource_id = make_int(request.args.get('id'))
    uuid = request.args.get('uuid')
    availability = request.args.get('availability')
    page = make_int(request.args.get('page', default=1, type=int))
    per_page = make_int(request.args.get('per_page', default=10, type=int))

    availability_dict = {
        "true": True,
        "false": False,
        None: None,
    }

    query = services.get_web_resources_query(
        left_join=True,
        domain_zone=domain_zone,
        resource_id=resource_id,
        resource_uuid=uuid,
        is_available=availability_dict.get(availability),
    )

    paginated_resource_list = models.WebResource.get_paginated(
        query,
        page,
        per_page,
        'main.get_resources',
    )

    response = schemas.PaginatedResourceListSchema(
        items=[
            schemas.ResourceGetSchema(**item).dict() for item in paginated_resource_list["items"]
        ],
        meta=paginated_resource_list.get('_meta'),
        links=paginated_resource_list.get('_links')
    ).dict()

    return jsonify(response)


@bp.route("/resources/", methods=['POST'])
def create_url():
    """
    Router for proceeding single URL from body or multiple URLs from zip with csv file.
    Create celery task if zip file was uploaded.
    """
    if request.is_json and not request.files:
        body = request.get_json()

        try:
            validated_url = schemas.ResourceCreateRequestSchema(**body)

            # check whether resource already exists in DB
            web_resource = services.create_web_resource(validated_url.url)

            if not web_resource:
                return jsonify({'error': 'Web resource already exists'}), 409

            else:
                response_data = schemas.ResourceCreateResponseSchema(
                    full_url=validated_url.url,
                    uuid=web_resource.uuid,
                    protocol=web_resource.protocol,
                    domain=web_resource.domain,
                    domain_zone=web_resource.domain_zone,
                    url_path=web_resource.url_path,
                    query_params=web_resource.query_params,
                )

                app.logger.info(f"201 - User posted new URL on {url_for('.create_url')}")

                return Response(
                    response_data.json(),
                    status=201,
                    mimetype='application/json',
                )

        except ValidationError as e:
            app.logger.info(f"400 - User made bad request to {request.url}")
            errors = convert_to_serializable(e.errors())
            response = {
                'error': 'Validation error',
                'message': errors,
            }
            return jsonify(response), 400

    elif request.files and not request.is_json:

        try:
            validated_data = schemas.ZipFileRequestSchema(**request.files)

            # create ZipFileProcessingRequest model instance
            processing_request_id = services.create_file_processing_request()

            # create celery task and pass id of created request to it as argument
            process_urls_from_zip_archive.delay(
                zip_file=validated_data.file.read(),
                request_id=processing_request_id,
            )

            app.logger.info(
                f"201 - User posted ZIP archive with URLs on {url_for('.create_url')}"
            )

            return (
                jsonify(
                    {
                        "_links":
                            {
                                "task": url_for(
                                    ".get_status_of_processing_request",
                                    request_id=processing_request_id,
                                    _external=True,
                                )
                            }
                    }
                ),
                201,
            )

        except ValidationError as e:
            errors = convert_to_serializable(e.errors())
            response = {
                'error': 'Validation error',
                'message': errors,
            }
            return jsonify(response), 400

    else:
        app.logger.info(
            f"400 - User made bad request to {url_for('.create_url')}"
        )
        return jsonify(
            {"Error": "Invalid request format. Send URL via JSON or zip archive via multipart/form-data."}
        ), 400


@bp.route("/resources/<int:web_resource_id>/", methods=['DELETE'])
def delete_url_structure(web_resource_id: int):
    found_and_deleted = services.delete_web_resource_by_id(web_resource_id)

    if found_and_deleted:
        app.logger.info(f"204 - Resource with ID={web_resource_id} was deleted.")
        return Response(status=204)
    else:
        app.logger.info(f"404 - Attempt to delete resource with ID={web_resource_id} that does not exist.")
        return Response(status=404)


@bp.route("/processing-requests/<int:request_id>/", methods=["GET"])
def get_status_of_processing_request(request_id: int):
    processing_request = services.get_file_processing_request_by_id(request_id=request_id)

    app.logger.info(f"200 - GET request to {request.url}")

    response = {
        "is_finished": processing_request.is_finished,
        "total_urls": processing_request.total_urls,
        "processed_urls": processing_request.processed_urls,
        "errors": processing_request.errors,
    }

    return jsonify(response)


@bp.route("/resources/<uuid:resource_uuid>/", methods=["POST"])
def post_image_for_resource(resource_uuid: str):
    """Router for posting images for resource with the given UUID."""
    resource = services.get_resource_by_uuid(resource_uuid)

    if not resource:
        app.logger.info(f"404 - POST request to {request.url} with ID that does not exist.")
        return Response(status=404)

    else:
        try:
            validated_data = schemas.FileRequestSchema(**request.files)
            services.add_image_to_resource(resource, validated_data.file)
            return Response(status=201)
        except ValidationError as e:
            # app.logger.info(f""")
            errors = convert_to_serializable(e.errors())
            response = {
                'error': 'Validation error',
                'message': errors,
            }
            return jsonify(response), 400


@socketio.on("connect", namespace="/logs")
def connect():
    # app.logger.info("Websocket connection to /logs page")
    logs = log_buffer
    socketio.emit(event="init_logs", data={"logs": logs}, namespace="/logs")


@bp.route("/resources/<uuid:resource_uuid>/", methods=["GET"])
def get_resource_page(resource_uuid):
    resource = services.get_resource_by_uuid(uuid_=resource_uuid)

    if not resource:
        return jsonify({"Error": "Not found"}), 404

    # TODO: change forming the response with Pydantic Schemas

    else:
        page = services.get_resource_page(resource_uuid=resource_uuid)
        data = []
        for item in page:
            news_item = item[1]  # NewsFeedItem находится на второй позиции в кортеже
            news_dict = {
                "event_type": news_item.event_type.value,
                "timestamp": news_item.timestamp.isoformat()
            }
            data.append(news_dict)

        if news_item.resource.screenshot:
            screenshot_base64 = b64encode(news_item.resource.screenshot).decode("utf-8")
        else:
            screenshot_base64 = None

        return jsonify(
            url=news_item.resource.full_url,
            url_path=news_item.resource.url_path,
            protocol=news_item.resource.protocol,
            domain=news_item.resource.domain,
            domain_zone=news_item.resource.domain_zone,
            screenshot=screenshot_base64,
            events=data,
        )
