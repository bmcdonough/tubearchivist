"""all API views"""

import logging
from appsettings.src.config import ReleaseVersion
from appsettings.src.reindex import ReindexProgress
from common.serializers import (
    AsyncTaskResponseSerializer,
    ErrorResponseSerializer,
    NotificationQueryFilterSerializer,
    NotificationSerializer,
    PingSerializer,
    RefreshAddDataSerializer,
    RefreshAddQuerySerializer,
    RefreshQuerySerializer,
    RefreshResponseSerializer,
    WatchedDataSerializer,
)
from common.src.searching import SearchForm
from common.src.ta_redis import RedisArchivist
from common.src.watched import WatchState
from common.views_base import AdminOnly, ApiBaseView
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView
from task.tasks import check_reindex


class PingView(ApiBaseView):
    """resolves to /api/ping/
    GET: test your connection
    """

    @staticmethod
    @extend_schema(
        responses={200: OpenApiResponse(PingSerializer())},
    )
    def get(request):
        """get pong"""
        logger = logging.getLogger(__name__)
        
        # Debug incoming request
        logger.info(f"🎯 [PING] Received /api/ping request from {request.META.get('REMOTE_ADDR')}")
        logger.debug(f"📡 [PING] Request method: {request.method}")
        logger.debug(f"🌐 [PING] Request headers: {dict(request.headers)}")
        logger.debug(f"🔑 [PING] Request user: {request.user} (authenticated: {request.user.is_authenticated})")
        meta_info = f"""📝 [PING] Request META: {{
            'CONTENT_TYPE': {request.META.get('CONTENT_TYPE')},
            'HTTP_ACCEPT': {request.META.get('HTTP_ACCEPT')},
            'HTTP_USER_AGENT': {request.META.get('HTTP_USER_AGENT')},
            'HTTP_ORIGIN': {request.META.get('HTTP_ORIGIN')},
            'HTTP_REFERER': {request.META.get('HTTP_REFERER')},
            'CSRF_COOKIE': {request.META.get('CSRF_COOKIE')}
        }}"""
        logger.debug(meta_info)
        
        try:
            # Check authentication state
            if request.user.is_anonymous:
                logger.warning("⚠️ [PING] User is anonymous - authentication required")
            else:
                logger.info(f"✅ [PING] User authenticated: ID={request.user.id}, username={request.user.username}")
            
            # Build response data
            data = {
                "response": "pong",
                "user": request.user.id if request.user.is_authenticated else None,
                "version": ReleaseVersion().get_local_version(),
                "ta_update": ReleaseVersion().get_update(),
            }
            logger.debug(f"📄 [PING] Response data: {data}")
            
            # Serialize response
            serializer = PingSerializer(data)
            logger.info("🚀 [PING] Successfully returning pong response")
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"❌ [PING] Exception in PingView: {type(e).__name__}: {str(e)}")
            logger.error(f"🔍 [PING] Exception traceback:", exc_info=True)
            raise


class RefreshView(ApiBaseView):
    """resolves to /api/refresh/
    GET: get refresh progress
    POST: start a manual refresh task
    """

    permission_classes = [AdminOnly]

    @extend_schema(
        responses={
            200: OpenApiResponse(RefreshResponseSerializer()),
            400: OpenApiResponse(
                ErrorResponseSerializer(), description="Bad request"
            ),
        },
        parameters=[RefreshQuerySerializer()],
    )
    def get(self, request):
        """get refresh status"""
        query_serializer = RefreshQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        validated_query = query_serializer.validated_data
        request_type = validated_query.get("type")
        request_id = validated_query.get("id")

        if request_id and not request_type:
            error = ErrorResponseSerializer(
                {"error": "specified id also needs type"}
            )
            return Response(error.data, status=400)

        try:
            progress = ReindexProgress(
                request_type=request_type, request_id=request_id
            ).get_progress()
        except ValueError:
            error = ErrorResponseSerializer({"error": "bad request"})
            return Response(error.data, status=400)

        response_serializer = RefreshResponseSerializer(progress)

        return Response(response_serializer.data)

    @extend_schema(
        request=RefreshAddDataSerializer(),
        responses={
            200: OpenApiResponse(AsyncTaskResponseSerializer()),
        },
        parameters=[RefreshAddQuerySerializer()],
    )
    def post(self, request):
        """add to reindex queue"""
        query_serializer = RefreshAddQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        validated_query = query_serializer.validated_data

        data_serializer = RefreshAddDataSerializer(data=request.data)
        data_serializer.is_valid(raise_exception=True)
        validated_data = data_serializer.validated_data

        extract_videos = validated_query.get("extract_videos")
        task = check_reindex.delay(
            data=validated_data, extract_videos=extract_videos
        )
        message = {
            "message": "reindex task started",
            "task_id": task.id,
        }
        serializer = AsyncTaskResponseSerializer(message)

        return Response(serializer.data)


class WatchedView(ApiBaseView):
    """resolves to /api/watched/
    POST: change watched state of video, channel or playlist
    """

    @extend_schema(
        request=WatchedDataSerializer(),
        responses={
            200: OpenApiResponse(WatchedDataSerializer()),
            400: OpenApiResponse(
                ErrorResponseSerializer(), description="Bad request"
            ),
        },
    )
    def post(self, request):
        """change watched state"""
        data_serializer = WatchedDataSerializer(data=request.data)
        data_serializer.is_valid(raise_exception=True)
        validated_data = data_serializer.validated_data
        youtube_id = validated_data.get("id")
        is_watched = validated_data.get("is_watched")

        if not youtube_id or is_watched is None:
            error = ErrorResponseSerializer(
                {"error": "missing id or is_watched"}
            )
            return Response(error.data, status=400)

        WatchState(youtube_id, is_watched, request.user.id).change()
        return Response(data_serializer.data)


class SearchView(ApiBaseView):
    """resolves to /api/search/
    GET: run a search with the string in the ?query parameter
    """

    @staticmethod
    def get(request):
        """handle get request
        search through all indexes"""
        search_query = request.GET.get("query", None)
        if search_query is None:
            return Response(
                {"message": "no search query specified"}, status=400
            )

        search_results = SearchForm().multi_search(search_query)
        return Response(search_results)


class NotificationView(ApiBaseView):
    """resolves to /api/notification/
    GET: returns a list of notifications
    filter query to filter messages by group
    """

    valid_filters = ["download", "settings", "channel"]

    @extend_schema(
        responses={
            200: OpenApiResponse(NotificationSerializer(many=True)),
        },
        parameters=[NotificationQueryFilterSerializer],
    )
    def get(self, request):
        """get all notifications"""
        query_serializer = NotificationQueryFilterSerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        validated_query = query_serializer.validated_data
        filter_by = validated_query.get("filter")

        query = "message"
        if filter_by in self.valid_filters:
            query = f"{query}:{filter_by}"

        notifications = RedisArchivist().list_items(query)
        response_serializer = NotificationSerializer(notifications, many=True)

        return Response(response_serializer.data)


class HealthCheck(APIView):
    """health check view, no auth needed"""

    def get(self, request):
        """health check, no auth needed"""
        return Response("OK", status=200)
