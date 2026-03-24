import csv
import datetime
from django.http import HttpResponse
from django.db.models import Max, Q
from django.db.models.functions import Upper
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.views import APIView
from .models import GlobalsDesignation, GlobalsHoldsdesignation, GlobalsModuleaccess, AuthUser, Batch, Student, GlobalsDepartmentinfo, Programme, GlobalsFaculty, Staff, AuditLog
from .serializers import GlobalExtraInfoSerializer, GlobalsDesignationSerializer, GlobalsModuleaccessSerializer, AuthUserSerializer, GlobalsHoldsDesignationSerializer, StudentSerializer, GlobalsFacultySerializer, GlobalsDepartmentinfoSerializer, BatchSerializer, ProgrammeSerializer, StaffSerializer, ViewStudentsWithFiltersSerializer, ViewStaffWithFiltersSerializer, ViewFacultyWithFiltersSerializer, AuditLogSerializer
from io import StringIO
from .helpers import create_password, send_email, mail_to_user, configure_password_mail, add_user_extra_info, add_user_designation_info, add_student_info, log_audit
from django.contrib.auth.hashers import make_password
from backend.settings import EMAIL_TEST_ARRAY
from django.conf import settings


@api_view(['GET'])
def get_all_departments(request):
    records = GlobalsDepartmentinfo.objects.all().order_by('id')
    serializer = GlobalsDepartmentinfoSerializer(records, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def get_all_batches(request):
    records = Batch.objects.distinct('year')
    serializer = BatchSerializer(records, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def get_all_programmes(request):
    records = Programme.objects.all().order_by('id')
    serializer = ProgrammeSerializer(records, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def get_user_role_by_username(request):
    username = request.query_params.get('username')
    
    if not username:
        return Response({"error": "Username parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = AuthUser.objects.get(username__iexact=username)
        holds_designation_entries = GlobalsHoldsdesignation.objects.filter(user=user)
        
        if not holds_designation_entries.exists():
            return Response({"error": "User has no designations."}, status=status.HTTP_404_NOT_FOUND)
        
        designation_ids = [entry.designation_id for entry in holds_designation_entries]
        
        roles = GlobalsDesignation.objects.filter(id__in=designation_ids)
        roles_serializer = GlobalsDesignationSerializer(roles, many=True)
        
        return Response({
            "user": AuthUserSerializer(user).data,
            "roles": roles_serializer.data,
        }, status=status.HTTP_200_OK)
        
    except AuthUser.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
def update_user_roles(request):
    username = request.data.get('username')
    roles_to_add = request.data.get('roles')

    if not username or not roles_to_add:
        return Response({"error": "Username and roles are required."}, status=status.HTTP_400_BAD_REQUEST)

    user = get_object_or_404(AuthUser, username__iexact=username)

    existing_roles = GlobalsHoldsdesignation.objects.filter(user=user)
    existing_role_names = set(existing_roles.values_list('designation__name', flat=True))

    processed_roles_to_add = set()

    for role in roles_to_add:
        if isinstance(role, dict):
            if 'name' in role:
                processed_roles_to_add.add(role['name'])
        elif isinstance(role, str):
            processed_roles_to_add.add(role)

    print("Processed roles_to_add:", processed_roles_to_add)

    roles_to_remove = existing_role_names - processed_roles_to_add

    GlobalsHoldsdesignation.objects.filter(user=user, designation__name__in=roles_to_remove).delete()

    for role_name in processed_roles_to_add:
        if role_name not in existing_role_names:
            designation = get_object_or_404(GlobalsDesignation, name=role_name)
            GlobalsHoldsdesignation.objects.create(
                held_at=timezone.now(),
                designation=designation,
                user=user,
                working=user
            )

    actor = request.data.get('performed_by', 'unknown')
    added = list(processed_roles_to_add - existing_role_names)
    removed = list(roles_to_remove)
    log_audit(
        actor=actor,
        action='ROLE_CHANGE',
        resource_type='role',
        target_user=username,
        details={'added': added, 'removed': removed},
        request=request,
    )

    return Response({"message": "User roles updated successfully."}, status=status.HTTP_200_OK)
        
@api_view(['GET'])
def global_designation_list(request):
    records = GlobalsDesignation.objects.all()
    serializer = GlobalsDesignationSerializer(records, many=True)
    return Response(serializer.data)

@api_view(['POST'])
def get_category_designations(request):
    category = request.data.get('category', 'student')
    basic = request.data.get('basic', True)
    records = GlobalsDesignation.objects.all().filter(category=category, basic=basic)
    serializer = GlobalsDesignationSerializer(records, many=True)
    return Response(serializer.data)

@api_view(['POST'])
def add_designation(request):
    serializer = GlobalsDesignationSerializer(data=request.data)
    if serializer.is_valid():
        role = serializer.save()
        max_id = GlobalsModuleaccess.objects.aggregate(Max('id'))['id__max']
        new_id = (max_id or 0) + 1
        data = {
            'id': new_id,
            'designation' : role.name,
            'program_and_curriculum' : False,
            'course_registration' : False,
            'course_management' : False,
            'other_academics' : False,
            'spacs' : False,
            'department' : False,
            'examinations' : False,
            'hr' : False,
            'iwd' : False,
            'complaint_management' : False,
            'fts' : False,
            'purchase_and_store' : False,
            'rspc' : False,
            'hostel_management' : False,
            'mess_management' : False,
            'gymkhana' : False,
            'placement_cell' : False,
            'visitor_hostel' : False,
            'phc' : False,
            'inventory_management': False,
        }
        module_serializer = GlobalsModuleaccessSerializer(data=data)
        if module_serializer.is_valid():
            module_serializer.save()
        actor = request.data.get('performed_by', 'unknown')
        log_audit(
            actor=actor,
            action='CREATE',
            resource_type='role',
            details={'role_name': role.name, 'role_type': role.type},
            request=request,
        )
        return Response({'role': serializer.data, 'modules': module_serializer.data}, status.HTTP_201_CREATED)
    else :
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)
    
@api_view(['PUT', 'PATCH'])
def update_designation(request):
    name = request.data.get('name')
    
    if not name:
        return Response({"error": "No name provided."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        designation = GlobalsDesignation.objects.get(name=name)
    except GlobalsDesignation.DoesNotExist:
        return Response({"error": f"Designation with name '{name}' not found."}, status=status.HTTP_404_NOT_FOUND)
    
    partial = request.method == 'PATCH'
    serializer = GlobalsDesignationSerializer(designation, data=request.data, partial=partial)
    
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def reset_password(request):
    user_name = request.data.get('username')
    try:
        user = AuthUser.objects.annotate(username_upper=Upper('username')).get(username_upper=user_name.upper())
        new_password = create_password(request.data)
        while new_password == user.password:
            new_password = create_password(request.data)
        
        user.password = new_password
        user.save()
        
        try:
            subject = 'Your Password has been reset!!'
            message = f"This Mail is to notify you that your password has been reset by the System Administrator.\n\nPlease check out the new password below:  {new_password}\n\nRegards,\nSystem Administrator,\nIIITDM Jabalpur."
            recipient_list = [f"{user.email}" if settings.EMAIL_TEST_MODE == 0 else settings.EMAIL_TEST_USER]
            send_email(subject=subject, message=message, recipient_list=recipient_list)
        except:
            print(e)
        finally:
            actor = request.data.get('performed_by', 'unknown')
            log_audit(
                actor=actor,
                action='RESET_PASSWORD',
                resource_type='user',
                target_user=user_name,
                request=request,
            )
            return Response({"password": new_password,"message": "Password reset successfully."}, status=status.HTTP_200_OK)
    except AuthUser.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_module_access(request):
    role_name = request.query_params.get('designation')
    
    if not role_name:
        return Response({"error": "No role provided."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        module_access = GlobalsModuleaccess.objects.get(designation=role_name)
    except GlobalsModuleaccess.DoesNotExist:
        return Response({"error": f"Module access for designation '{role_name}' not found."}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = GlobalsModuleaccessSerializer(module_access)
    return Response(serializer.data, status=status.HTTP_200_OK)
    
@api_view(['PUT'])
def modify_moduleaccess(request):
    role_name = request.data.get('designation')
    
    if not role_name:
        return Response({"error": "No role provided."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        designation = GlobalsModuleaccess.objects.get(designation=role_name)
    except GlobalsModuleaccess.DoesNotExist:
        return Response({"error": f"Designation with name '{role_name}' not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = GlobalsModuleaccessSerializer(designation, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        actor = request.data.get('performed_by', 'unknown')
        log_audit(
            actor=actor,
            action='MODULE_ACCESS_CHANGE',
            resource_type='role',
            details={'designation': role_name},
            request=request,
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def add_individual_student(request):
    required_fields = ["username", "first_name", "last_name", "sex", "category", "father_name", "mother_name", "batch", "programme"]
    data = request.data
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    if missing_fields:
        return Response({
            "error": "Missing required fields.",
            "missing_fields": missing_fields
        }, status=status.HTTP_400_BAD_REQUEST)
    user_password = create_password(data)
    
    auth_user_data = {
        "password": make_password(user_password),
        "username": data['username'].upper(),
        "first_name": data['first_name'],
        "last_name": data.get('last_name', ""),
        "email": f"{data['username'].lower()}@iiitdmj.ac.in",
        "is_staff": False,
        "is_superuser": False,
        "is_active": True,
        "date_joined": datetime.datetime.now().strftime("%Y-%m-%d"),
    }
    auth_serializer = AuthUserSerializer(data=auth_user_data)
    user = None
    if auth_serializer.is_valid():
        user = auth_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to auth user table",
            "data": auth_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    default_department = GlobalsDepartmentinfo.objects.get(name='CSE').id
    extra_info_data = {
        'id': data['username'].upper(),
        'title': data.get('title') if data.get('title') else 'Mr.' if data['sex'][0].upper() == 'M' else 'Ms.',
        'sex': data['sex'][0].upper(),
        'date_of_birth': data.get("dob") if data.get("dob") else "2025-01-01",
        'user_status': "PRESENT",
        'address': data.get("address") if data.get("address") else "NA",
        'phone_no': data.get("phone") if data.get("phone") else 9999999999,
        'about_me': "NA",
        'user_type': 'student',
        'profile_picture': None,
        'date_modified': datetime.datetime.now().strftime("%Y-%m-%d"),
        'department': data.get("department") if data.get("department") else default_department,
        'user': user.id,
    }
    extra_info_serializer = GlobalExtraInfoSerializer(data=extra_info_data)
    extra_info = None
    if extra_info_serializer.is_valid():
        extra_info = extra_info_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to globals extra info table",
            "data": extra_info_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    designation_id = GlobalsDesignation.objects.get(name='student').id
    holds_designation_data = {
        'designation' : designation_id,
        'user' : user.id,
        'working' : user.id,
    }
    holds_designation_serializer = GlobalsHoldsDesignationSerializer(data=holds_designation_data)
    if holds_designation_serializer.is_valid():
        holds_designation_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to globals holds designation table",
            "data": holds_designation_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    batch = Batch.objects.filter(name = data.get('programme'), discipline__acronym = extra_info.department.name, year = data.get('batch')).first()
    student_data = {
        'id' : extra_info.id,
        'programme' : data.get('programme') if data.get('programme') else 'B.Tech',
        'batch' : data.get('batch') if data.get('batch') else datetime.datetime.now().year,
        'batch_id' : batch.id if batch else None,
        'cpi': 0.0,
        'category' : data['category'].upper() if data['category'].upper() else 'GEN',
        'father_name' : data.get('father_name') if data.get('father_name') else None,
        'mother_name' : data.get('mother_name') if data.get('mother_name') else None,
        'hall_no': data.get('hall_no') if data.get('hall_no') else 3,
        'room_no': None,
        'specialization': None,
        'curr_semester_no' : 2*(datetime.datetime.now().year - data.get('batch')) + datetime.datetime.now().month // 7,
    }
    student_data_serializer = StudentSerializer(data=student_data)
    if student_data_serializer.is_valid():
        student_data_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to academic information student table",
            "data": student_data_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    actor = request.data.get('performed_by', 'unknown')
    log_audit(
        actor=actor,
        action='CREATE',
        resource_type='student',
        target_user=data['username'].upper(),
        details={'programme': data.get('programme'), 'batch': data.get('batch')},
        request=request,
    )

    response_data = {
        "message": f"1 user created successfully.",
        "created_users": [auth_serializer.data],
        "skipped_users_count": 0,
    }

    return Response(response_data, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def add_individual_staff(request):
    required_fields = ["username", "first_name", "last_name", "sex", "designation"]
    data = request.data
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    if missing_fields:
        return Response({
            "error": "Missing required fields.",
            "missing_fields": missing_fields
        }, status=status.HTTP_400_BAD_REQUEST)
    user_password = create_password(data)
    auth_user_data = {
        "password": make_password(user_password),
        "username": data['username'].lower(),
        "first_name": data['first_name'].lower().capitalize(),
        "last_name": data.get('last_name').lower().capitalize(),
        "email": f"{data['username'].lower()}@iiitdmj.ac.in",
        "is_staff": True,
        "is_superuser": False,
        "is_active": True,
        "date_joined": datetime.datetime.now().strftime("%Y-%m-%d"),
    }
    auth_serializer = AuthUserSerializer(data=auth_user_data)
    user = None
    if auth_serializer.is_valid():
        user = auth_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to auth user table",
            "data": auth_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    default_department = GlobalsDepartmentinfo.objects.get(name='CSE').id
    extra_info_data = {
        'id': data['username'].lower(),
        'title': data.get('title') if data.get('title') else 'Mr.' if data['sex'][0].upper() == 'M' else 'Ms.',
        'sex': data['sex'][0].upper(),
        'date_of_birth': data.get("dob") if data.get("dob") else "2025-01-01",
        'user_status': "PRESENT",
        'address': data.get("address") if data.get("address") else "NA",
        'phone_no': data.get("phone") if data.get("phone") else 9999999999,
        'about_me': "NA",
        'user_type': 'staff',
        'profile_picture': None,
        'date_modified': datetime.datetime.now().strftime("%Y-%m-%d"),
        'department': data.get("department") if data.get("department") else default_department,
        'user': user.id,
    }
    extra_info_serializer = GlobalExtraInfoSerializer(data=extra_info_data)
    extra_info = None
    if extra_info_serializer.is_valid():
        extra_info = extra_info_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to globals extra info table",
            "data": extra_info_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    holds_designation_data = {
        'designation' : data.get('designation'),
        'user' : user.id,
        'working' : user.id,
    }
    holds_designation_serializer = GlobalsHoldsDesignationSerializer(data=holds_designation_data)
    if holds_designation_serializer.is_valid():
        holds_designation_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to globals holds designation table",
            "data": holds_designation_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    staff_id = extra_info.id
    staff_data = {
        'id' : staff_id,
    }

    staff_serializer = GlobalsFacultySerializer(data=staff_data)
    if staff_serializer.is_valid():
        staff_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to globals staff table",
            "data": staff_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    actor = request.data.get('performed_by', 'unknown')
    log_audit(
        actor=actor,
        action='CREATE',
        resource_type='staff',
        target_user=data['username'].lower(),
        details={'designation': data.get('designation')},
        request=request,
    )

    return Response({
        "message": "Staff added successfully",
        "auth_user_data": auth_user_data,
        "extra_info_user_data": extra_info_data,
        "holds_designation_user_data": holds_designation_data,
        "globals_staff_data": staff_data,
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def add_individual_faculty(request):
    required_fields = ["username", "first_name", "last_name", "sex", "designation"]
    data = request.data
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    if missing_fields:
        return Response({
            "error": "Missing required fields.",
            "missing_fields": missing_fields
        }, status=status.HTTP_400_BAD_REQUEST)
    user_password = create_password(data)
    auth_user_data = {
        "password": make_password(user_password),
        "username": data['username'].lower(),
        "first_name": data['first_name'].lower().capitalize(),
        "last_name": data.get('last_name').lower().capitalize(),
        "email": f"{data['username'].lower()}@iiitdmj.ac.in",
        "is_staff": False,
        "is_superuser": False,
        "is_active": True,
        "date_joined": datetime.datetime.now().strftime("%Y-%m-%d"),
    }
    auth_serializer = AuthUserSerializer(data=auth_user_data)
    user = None
    if auth_serializer.is_valid():
        user = auth_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to auth user table",
            "data": auth_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    default_department = GlobalsDepartmentinfo.objects.get(name='CSE').id
    extra_info_data = {
        'id': data['username'].lower(),
        'title': data.get('title') if data.get('title') else 'Mr.' if data['sex'][0].upper() == 'M' else 'Ms.',
        'sex': data['sex'][0].upper(),
        'date_of_birth': data.get("dob") if data.get("dob") else "2025-01-01",
        'user_status': "PRESENT",
        'address': data.get("address") if data.get("address") else "NA",
        'phone_no': data.get("phone") if data.get("phone") else 9999999999,
        'about_me': "NA",
        'user_type': 'faculty',
        'profile_picture': None,
        'date_modified': datetime.datetime.now().strftime("%Y-%m-%d"),
        'department': data.get("department") if data.get("department") else default_department,
        'user': user.id,
    }
    extra_info_serializer = GlobalExtraInfoSerializer(data=extra_info_data)
    extra_info = None
    if extra_info_serializer.is_valid():
        extra_info = extra_info_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to globals extra info table",
            "data": extra_info_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    holds_designation_data = {
        'designation' : data.get('designation'),
        'user' : user.id,
        'working' : user.id,
    }
    holds_designation_serializer = GlobalsHoldsDesignationSerializer(data=holds_designation_data)
    if holds_designation_serializer.is_valid():
        holds_designation_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to globals holds designation table",
            "data": holds_designation_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    faculty_id = extra_info.id
    faculty_data = {
        'id' : faculty_id,
    }

    faculty_serializer = GlobalsFacultySerializer(data=faculty_data)
    if faculty_serializer.is_valid():
        faculty_serializer.save()
    else:
        return Response({
            "message": "Error in adding user to globals faculty table",
            "data": faculty_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    actor = request.data.get('performed_by', 'unknown')
    log_audit(
        actor=actor,
        action='CREATE',
        resource_type='faculty',
        target_user=data['username'].lower(),
        details={'designation': data.get('designation')},
        request=request,
    )

    return Response({
        "message": "Faculty added successfully",
        "auth_user_data": auth_user_data,
        "extra_info_user_data": extra_info_data,
        "holds_designation_user_data": holds_designation_data,
        "globals_faculty_data": faculty_data,
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def bulk_import_users(request):
    # CSV file headers:
    # 1 username
    # 2 first_name
    # 3 last_name
    # 4 sex
    # 5 category
    # 6 father_name
    # 7 mother_name
    # 8 batch
    # 9 programme
    # 10 title
    # 11 dob
    # 12 address
    # 13 phone_no
    # 14 department
    if 'file' not in request.FILES:
        return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
    
    file = request.FILES['file']
    if not file.name.endswith('.csv'):
        return Response({"error": "Please upload a valid CSV file."}, status=status.HTTP_400_BAD_REQUEST)

    file_data = file.read().decode('utf-8')
    csv_data = csv.reader(StringIO(file_data))
    
    headers = next(csv_data)
    created_users = []
    failed_users = []
    
    for row in csv_data:
        if len(row) < 9:
            failed_users.append(row)
            continue
        try:
            user_data = {
                'password': make_password("user@123"),
                'username': row[0].upper(),
                'first_name': row[1].lower().capitalize() if len(row[1]) > 0 else 'NA',
                'last_name': row[2].lower().capitalize() if len(row[2]) > 0 else 'NA',
                'email': f"{row[0].lower()}@iiitdmj.ac.in",
                'is_staff': False,
                'is_superuser': False,
                'is_active': True,
                'date_joined': datetime.datetime.now().strftime("%Y-%m-%d"),
            }
            serializer = AuthUserSerializer(data=user_data)
            user = None
            if serializer.is_valid():
                user = serializer.save()
            extra_info_serializer = add_user_extra_info(row, user)
            extra_serializer = None
            if extra_info_serializer:
                extra_serializer = extra_info_serializer.save()
            role_serializer = add_user_designation_info(user.id)
            if role_serializer:
                role_serializer.save()
            student_serializer = add_student_info(row, extra_serializer)
            if student_serializer:
                student_serializer.save()
            if user and extra_info_serializer and role_serializer and student_serializer:
                created_users.append(serializer.data)
        except Exception as e:
            print("error",e)
            failed_users.append(row)

    if(len(created_users) > 0):
        mail_to_user(created_users)

    actor = request.data.get('performed_by', 'unknown')
    log_audit(
        actor=actor,
        action='BULK_IMPORT',
        resource_type='student',
        details={'created': len(created_users), 'skipped': len(failed_users)},
        request=request,
    )

    response_data = {
        "message": f"{len(created_users)} users created successfully.",
        "created_users": created_users,
        "skipped_users_count": len(failed_users),
    }

    if failed_users:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        for failed_user in failed_users:
            writer.writerow(failed_user)

        output.seek(0)
        response_data["skipped_users_csv"] = output.getvalue()

    return Response(response_data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def bulk_export_users(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['username', 'first_name', 'last_name', 'email', 'is_staff', 'is_superuser'])
    users = AuthUser.objects.all()
    
    for user in users:
        writer.writerow([user.username, user.first_name, user.last_name, user.email, user.is_staff, user.is_superuser])
    
    return response

@api_view(['POST'])
def mail_to_whole_batch(request):
    emails = EMAIL_TEST_ARRAY
    email_list = emails.split(',')
    if(len(email_list) != 1):
        students = Student.objects.filter(batch=request.data.get('batch'), id__user__email__in=email_list)
    else:
        students = Student.objects.filter(batch=request.data.get('batch'))
        
    students_data = [student.id.user for student in students]
    try:
        configure_password_mail(students_data)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response({"message": "Mail sent to whole batch successfully."}, status=status.HTTP_200_OK)

def download_sample_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "username", "first_name", "last_name", "sex", "category",
        "father_name", "mother_name", "batch", "programme", "title",
        "dob", "address", "phone_no", "department"
    ])
    return response

class UserListView(APIView):
    def get(self, request):
        user_type = request.GET.get('type')
        serializer = None

        if user_type == "student":
            students = Student.objects.select_related('id__user', 'id__department', 'batch_id')
            programme = request.GET.get("programme")
            batch = request.GET.get("batch")
            discipline = request.GET.get("discipline")
            category = request.GET.get("category")
            gender = request.GET.get("gender")

            if programme:
                students = students.filter(programme__iexact=programme)
            if batch:
                students = students.filter(batch=batch)
            if discipline:
                students = students.filter(batch_id__discipline__name__iexact=discipline)
            if category:
                students = students.filter(category__iexact=category)
            if gender:
                students = students.filter(id__sex__iexact=gender)

            serializer = ViewStudentsWithFiltersSerializer(students, many=True)

        elif user_type == "faculty":
            faculty = GlobalsFaculty.objects.select_related('id__user', 'id__department').prefetch_related('id__user__holds_designations__designation')
            designation = request.GET.get("designation")
            gender = request.GET.get("gender")

            if designation:
                faculty = faculty.filter(id__user__holds_designations__designation__name__iexact=designation).distinct()
            if gender:
                faculty = faculty.filter(id__sex__iexact=gender)

            serializer = ViewFacultyWithFiltersSerializer(faculty, many=True)

        elif user_type == "staff":
            staff = Staff.objects.select_related("id__user", "id__department").prefetch_related('id__user__holds_designations__designation')
            designation = request.GET.get("designation")
            gender = request.GET.get("gender")

            if designation:
                staff = staff.filter(id__user__holds_designations__designation__name__iexact=designation).distinct()
            if gender:
                staff = staff.filter(id__sex__iexact=gender)

            serializer = ViewStaffWithFiltersSerializer(staff, many=True)

        else:
            return Response({"error": "Invalid or missing user type."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data)


@api_view(['GET'])
def get_audit_logs(request):
    logs = AuditLog.objects.all()
    actor = request.query_params.get('actor')
    action = request.query_params.get('action')
    resource_type = request.query_params.get('resource_type')
    if actor:
        logs = logs.filter(actor__icontains=actor)
    if action:
        logs = logs.filter(action=action)
    if resource_type:
        logs = logs.filter(resource_type__icontains=resource_type)
    logs = logs[:200]
    serializer = AuditLogSerializer(logs, many=True)
    return Response(serializer.data)
