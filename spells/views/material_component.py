from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from spells.models import MaterialComponent


class MaterialComponentSerializer(serializers.ModelSerializer):
    """Сериализатор данных для модели MaterialComponent"""

    class Meta:
        model = MaterialComponent
        fields = ["name", "description", "cost", "is_consumable", "is_focus"]

    def validate_name(self, value):
        """Валидация имени"""
        if len(value) > 49:
            raise serializers.ValidationError("Максимум 49 символов")
        return value

    def validate_cost(self, value):
        """Валидация стоимости"""
        if value and value < 0:
            raise serializers.ValidationError("Стоимость не может быть отрицательной")
        return value


"""API по пути /api/spells/material_component/"""


class MaterialConponentListView(APIView):
    def get(self, request: Request):
        """Получение всех компонент"""
        # Получаем все объекты (READ)
        components = MaterialComponent.objects.all()
        # Настраиваем сериализатор данных
        serializer = MaterialComponentSerializer(components, many=True)
        # Отправляем данные с ответом 200
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request):
        """Создание нового материального компонента"""
        # Десериализация данных, настройка сериализатора
        serializer = MaterialComponentSerializer(data=request.data)
        # Проверка валидности данных, при неправильных данных отправит ошибку
        serializer.is_valid(raise_exception=True)
        # Создание нового компонента в базе
        serializer.save()
        # Отправление ответ с кодом 201 (created) и созданный объект
        return Response(data=serializer.data, status=status.HTTP_201_CREATED)


class MaterialComponentDetailView(APIView):
    def get(self, request: Request, id: int):
        """Получение компонента по id"""
        # Находит объект по id или выходит из запроса с кодом 404 (not found)
        component = get_object_or_404(MaterialComponent, id=id)
        # Настраиваем сериализатор
        serializer = MaterialComponentSerializer(component)
        # Возвращение данных и статуса 200
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    def put(self, request: Request, id: int):
        """Полное обновление компонента"""
        # Находит объект по id или выходит из запроса с кодом 404 (not found)
        component = get_object_or_404(MaterialComponent, id=id)
        # Сериализатор сам заменяет данные в существующем объекте
        serializer = MaterialComponentSerializer(component, data=request.data)
        # Проверка валидности данных
        serializer.is_valid(raise_exception=True)
        # Сохранение измененного объекта
        serializer.save()
        # Возвращение измененного ответа и статуса 200
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    def patch(self, request: Request, id: int):
        """Частичное обновление компонента"""
        # Находит объект по id или выходит из запроса с кодом 404 (not found)
        component = get_object_or_404(MaterialComponent, id=id)
        # Настройка сериализатора с параметром partial
        serializer = MaterialComponentSerializer(
            component, data=request.data, partial=True
        )
        # Проверка валидности данных
        serializer.is_valid(raise_exception=True)
        # Сохранение обновленного компонента
        serializer.save()
        # Возвращение измененного ответа и статуса 200
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    def delete(self, request: Request, id: int):
        """Удаление компонента"""
        # Находит объект по id или выходит из запроса с кодом 404 (not found)
        component = get_object_or_404(MaterialComponent, id=id)
        # Удаление объекта из базы
        component.delete()
        # Возвращение успешного статуса 204 (no content)
        return Response(status=status.HTTP_204_NO_CONTENT)
