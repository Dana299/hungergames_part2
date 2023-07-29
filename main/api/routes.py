from flask import Response, jsonify, request, url_for
from pydantic import ValidationError

from main import app, bp, log_buffer, socketio
from main.service import db, exceptions, handlers
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

    response = handlers.handle_get_resources_with_filters(
        domain_zone=domain_zone,
        resource_id=resource_id,
        availability=availability,
        page=page,
        per_page=per_page,
        uuid=uuid,
    )

    return jsonify(response.dict())


@bp.route("/resources/", methods=['POST'])
def create_url():
    """
    Router for proceeding single URL from body or multiple URLs from zip with csv file.
    Create celery task if zip file was uploaded.
    """
    if request.is_json:
        body = request.get_json()

        try:
            url = handlers.handle_post_url_json(body)

            app.logger.info(f"201 - User posted new URL on {url_for('.create_url')}")

            return Response(
                url.json(),
                status=201,
                mimetype='application/json',
            )

        except exceptions.AlreadyExistsError:
            return jsonify({'error': 'Web resource already exists'}), 409

        except ValidationError as e:
            app.logger.info(f"400 - User made bad request to {request.url}")
            errors = convert_to_serializable(e.errors())
            response = {
                'error': 'Validation error',
                'message': errors,
            }
            return jsonify(response), 400

    elif request.files:

        try:
            processing_request_id = handlers.handle_post_url_file(request.files)

            app.logger.info(
                f"201 - User posted ZIP archive with URLs on {url_for('.create_url')}"
            )

            return jsonify({"request_id": processing_request_id}), 201

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
    try:
        db.delete_web_resource_by_id(web_resource_id)
        app.logger.info(f"204 - Resource with ID={web_resource_id} was deleted.")
        return Response(status=204)

    except exceptions.NotFoundError:
        app.logger.info(f"404 - Attempt to delete resource with ID={web_resource_id} that does not exist.")
        return Response(status=404)


@bp.route("/processing-requests/<int:request_id>/", methods=["GET"])
def get_status_of_processing_request(request_id: int):

    try:
        status_info = handlers.handle_get_request_status(
            request_id=request_id,
            storage_client=app.extensions["redis"],
        )
        return jsonify(status_info)

    except exceptions.NotFoundError:
        app.logger.info(f"404 - GET request to {request.url} with non-existing ID")
        return jsonify({"Error": "Request with the given ID was not found."}), 404


@bp.route("/resources/<uuid:resource_uuid>/", methods=["POST"])
def post_image_for_resource(resource_uuid: str):
    """Router for posting images for resource with the given UUID."""
    resource = db.get_resource_by_uuid(resource_uuid)

    if not resource:
        app.logger.info(f"404 - POST request to {request.url} with ID that does not exist.")
        return Response(status=404)

    else:
        if request.files:
            try:
                handlers.handle_post_image(request.files, resource)
                return Response(status=201)

            except ValidationError as e:
                # app.logger.info(f""")
                errors = convert_to_serializable(e.errors())
                response = {
                    'error': 'Validation error',
                    'message': errors,
                }
                return jsonify(response), 400

        else:
            return jsonify({"Error": "Invalid request format"}), 400


@bp.route("/resources/<uuid:resource_uuid>/", methods=["GET"])
def get_resource_page(resource_uuid):
    try:
        web_resource_data = handlers.handle_get_resource_data(resource_uuid)
    except exceptions.NotFoundError:
        return jsonify({"Error": "Resource with the given UUID not found."})

    return jsonify(web_resource_data.dict())


@bp.route("/logs/", methods=["GET"])
def get_logs():
    # TODO: put logs from buffer and return as response
    ...
    return jsonify()


@socketio.on("connect", namespace="/logs")
def connect():
    # app.logger.info("Websocket connection to /logs page")
    logs = log_buffer
    socketio.emit(event="init_logs", data={"logs": logs}, namespace="/logs")
