from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.user_register, name='register'),
    path('', views.dashboard, name='dashboard'),
    path('upload/', views.upload_record, name='upload_record'),
    path('records/', views.record_list, name='record_list'),
    path('records/<int:record_id>/', views.record_detail, name='record_detail'),
    path('records/<int:record_id>/delete/', views.delete_record, name='delete_record'),
    path('revalidate-all/', views.revalidate_all, name='revalidate_all'),
    path('map/', views.map_view, name='map_view'),
    path('api/map-data/', views.map_data_api, name='map_data_api'),
    path('api/chatbot/', views.chatbot_reply, name='chatbot_reply'),
    path('generate-mock-map/', views.generate_mock_map_data_view, name='generate_mock_map'),
]
