from diary.models import DiaryUser, Post
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
	post_chars = serializers.CharField(source='get_post_characters')
	posts_avg_chars = serializers.CharField(source='get_average_post_length')
	streak = serializers.CharField(source='get_streak')
	posts_count = serializers.IntegerField(source='posts.count')

	class Meta:
		model = DiaryUser
		fields = [
			'username',
			'email',
			'email_verified',
			'language',
			'is_staff',
			'post_chars',
			'posts_avg_chars',
			'posts_count',
			'streak',
		]


class PostSerializer(serializers.ModelSerializer):
	public_text = serializers.CharField(source='get_public_text')

	class Meta:
		model = Post
		fields = [
			'id',
			'date',
			'public_text',
			'mood',
			'image',
			'location_lat',
			'location_lon',
			'location_verbose',
			'public',
			'part_of',
			'natural_language',
			'is_editable'
		]


class PrivatePostSerializer(PostSerializer):
	# Like PostSerializer, but also includes clear text
	class Meta:
		model = Post
		fields = PostSerializer.Meta.fields + ['text']


class LeaderboardSerializer(serializers.Serializer):
	number_of_posts = serializers.ListField(child=serializers.DictField(child=serializers.CharField()))
	average_post_length = serializers.ListField(child=serializers.DictField(child=serializers.CharField()))
	longest_current_streak = serializers.ListField(child=serializers.DictField(child=serializers.CharField()))
