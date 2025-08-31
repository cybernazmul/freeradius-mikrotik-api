#!/bin/bash

# RADIUS Service Deployment Test Script

echo "🧪 Testing RADIUS Service Deployment"
echo "===================================="

API_KEY="your-secret-bearer-token-here"
BASE_URL="http://localhost:8000"

# Test 1: API Health Check
echo "1️⃣  Testing API Health..."
health_response=$(curl -s $BASE_URL/health)
if echo "$health_response" | grep -q "healthy"; then
    echo "   ✅ API Health Check: PASSED"
else
    echo "   ❌ API Health Check: FAILED"
    echo "   Response: $health_response"
    exit 1
fi

# Test 2: API Authentication
echo "2️⃣  Testing API Authentication..."
auth_response=$(curl -s -H "Authorization: Bearer $API_KEY" $BASE_URL/)
if echo "$auth_response" | grep -q "RADIUS Management API is running"; then
    echo "   ✅ API Authentication: PASSED"
else
    echo "   ❌ API Authentication: FAILED"
    echo "   Response: $auth_response"
    exit 1
fi

# Test 3: User Management
echo "3️⃣  Testing User Management..."
# Create user
create_response=$(curl -s -X POST "$BASE_URL/user" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser2",
    "passwd": "testpass2",
    "expdate": "2025-12-31",
    "package": "basic_package"
  }')

if echo "$create_response" | grep -q "User created successfully"; then
    echo "   ✅ User Creation: PASSED"
    
    # Get user
    get_response=$(curl -s -H "Authorization: Bearer $API_KEY" $BASE_URL/user/testuser2)
    if echo "$get_response" | grep -q "testuser2"; then
        echo "   ✅ User Retrieval: PASSED"
    else
        echo "   ❌ User Retrieval: FAILED"
    fi
    
    # Delete user
    delete_response=$(curl -s -X DELETE -H "Authorization: Bearer $API_KEY" $BASE_URL/user/testuser2)
    if echo "$delete_response" | grep -q "User deleted successfully"; then
        echo "   ✅ User Deletion: PASSED"
    else
        echo "   ❌ User Deletion: FAILED"
    fi
else
    echo "   ❌ User Creation: FAILED"
    echo "   Response: $create_response"
fi

# Test 4: Database Connection
echo "4️⃣  Testing Database Connection..."
db_test=$(docker exec radius-db mysql -u radius -pradiuspass radius -e "SELECT COUNT(*) as count FROM radcheck" 2>/dev/null)
if echo "$db_test" | grep -q "count"; then
    echo "   ✅ Database Connection: PASSED"
else
    echo "   ❌ Database Connection: FAILED"
fi

# Test 5: FreeRADIUS Status
echo "5️⃣  Testing FreeRADIUS Server..."
if docker exec freeradius-server ps aux | grep -q radiusd; then
    echo "   ✅ FreeRADIUS Process: RUNNING"
else
    echo "   ❌ FreeRADIUS Process: NOT RUNNING"
fi

# Test 6: Service Status
echo "6️⃣  Testing Service Status..."
echo "   📊 Service Status:"
docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🎉 RADIUS Service Deployment Test Complete!"
echo ""
echo "📚 API Documentation: http://localhost:8000/docs"
echo "🔑 API Key: $API_KEY"
echo "🐳 FreeRADIUS: UDP 1812 (auth), 1813 (acct), 3799 (CoA)"
echo "🗄️  MySQL: localhost:3306"