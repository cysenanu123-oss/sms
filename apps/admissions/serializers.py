# apps/admissions/serializers.py
from rest_framework import serializers
from .models import StudentApplication


class StudentApplicationSerializer(serializers.ModelSerializer):
    """Serializer for student application submissions"""
    
    class Meta:
        model = StudentApplication
        fields = [
            'application_number', 'department', 'learner_name', 'sex',
            'date_of_birth', 'age', 'applying_for_class', 'previous_school',
            'residential_address', 'nationality', 'region', 'languages_spoken',
            'religion', 'has_health_challenge', 'health_challenge_details',
            'has_allergies', 'allergies_details', 'medication_details',
            'insurance_company', 'insurance_number', 'insurance_card',
            'parents_status', 'declaration_name', 'signature', 'declaration_date',
            'status', 'submitted_at'
        ]
        read_only_fields = ['application_number', 'status', 'submitted_at']
    
    def validate_age(self, value):
        """Ensure age is reasonable"""
        if value < 1 or value > 25:
            raise serializers.ValidationError("Age must be between 1 and 25 years")
        return value
    
    def validate(self, data):
        """Additional validation"""
        # If health challenge is true, details must be provided
        if data.get('has_health_challenge') and not data.get('health_challenge_details'):
            raise serializers.ValidationError({
                'health_challenge_details': 'Please provide health challenge details'
            })
        
        # If allergies is true, details must be provided
        if data.get('has_allergies') and not data.get('allergies_details'):
            raise serializers.ValidationError({
                'allergies_details': 'Please provide allergy details'
            })
        
        return data