# services/cj_service.py - COMPLETE FIXED VERSION WITH PROPER VARIANT FETCHING

import requests
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from builder.models import *

logger = logging.getLogger(__name__)


class CJServiceException(Exception):
    """Base exception for CJ service errors"""
    pass


class CJAuthenticationException(CJServiceException):
    """Authentication failed"""
    pass


class CJOrderRequest:
    """Order request data model"""
    def __init__(self, **kwargs):
        self.order_no = kwargs.get('order_no')
        self.shipping_country_code = kwargs.get('shipping_country_code')
        self.product_list = kwargs.get('product_list', [])
        self.buyer_info = kwargs.get('buyer_info', {})
        self.warehouse = kwargs.get('warehouse', 'CN')
        self.shipping_method = kwargs.get('shipping_method')
        self.currency = kwargs.get('currency', 'USD')


class CJService:
    BASE_URL = "https://developers.cjdropshipping.com/api2.0/v1"

    def __init__(self, token):
        self.headers = {
            "CJ-Access-Token": token,
            "Content-Type": "application/json"
        }

    def get_warehouses(self):
        """Fetches all available CJ global warehouses."""
        url = f"{self.BASE_URL}/product/stock/getWarehouseList"
        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            data = response.json()
            return data.get('data', []) if data.get('code') == 200 else []
        except Exception as e:
            logger.error(f"Error fetching warehouses: {e}")
            return []

    def get_stock_by_vid(self, vid, pid=None):
        """
        Fetches stock for a variant using CJ API.
        Handles the actual response structure from CJ.
        """
        # ===== METHOD 1: Primary stock endpoint =====
        try:
            url = f"{self.BASE_URL}/product/stock/queryByVid"
            params = {"vid": vid}
            print(f"📡 Trying: {url}?vid={vid}")
            
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            data = response.json()
            
            if data.get('code') == 200:
                stock_data = data.get('data', [])
                if stock_data:
                    total_stock = 0
                    for item in stock_data:
                        # ===== USE THE CORRECT FIELD NAMES =====
                        # CJ returns these fields for stock:
                        # - storageNum (actual stock)
                        # - totalInventoryNum (total inventory)
                        # - factoryInventoryNum (factory stock)
                        stock_num = item.get('storageNum') or item.get('totalInventoryNum') or item.get('factoryInventoryNum') or 0
                        try:
                            total_stock += int(stock_num)
                        except (ValueError, TypeError):
                            pass
                    
                    if total_stock > 0:
                        print(f"✅ Stock found via stock/queryByVid: {total_stock}")
                        return [{'stockNum': total_stock, 'warehouseCode': item.get('countryCode', 'CN')}]
                    else:
                        print(f"⚠️ stock/queryByVid returned 0 stock")
            else:
                print(f"⚠️ stock/queryByVid returned {data.get('code')}: {data.get('message')}")
        except Exception as e:
            print(f"⚠️ Error with stock/queryByVid: {e}")
        
        # ===== METHOD 2: Try with warehouse parameter =====
        try:
            url = f"{self.BASE_URL}/product/stock/queryByVid"
            params = {"vid": vid, "warehouseCode": "CN"}
            print(f"📡 Trying: {url}?vid={vid}&warehouseCode=CN")
            
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            data = response.json()
            
            if data.get('code') == 200:
                stock_data = data.get('data', [])
                if stock_data:
                    total_stock = 0
                    for item in stock_data:
                        stock_num = item.get('storageNum') or item.get('totalInventoryNum') or item.get('factoryInventoryNum') or 0
                        try:
                            total_stock += int(stock_num)
                        except (ValueError, TypeError):
                            pass
                    
                    if total_stock > 0:
                        print(f"✅ Stock found via stock/queryByVid with warehouse: {total_stock}")
                        return [{'stockNum': total_stock, 'warehouseCode': 'CN'}]
        except Exception as e:
            print(f"⚠️ Error with stock/queryByVid (warehouse): {e}")
        
        # ===== METHOD 3: Stock list endpoint =====
        if pid:
            try:
                url = f"{self.BASE_URL}/product/stock/list"
                params = {"pid": pid}
                print(f"📡 Trying: {url}?pid={pid}")
                
                response = requests.get(url, headers=self.headers, params=params, timeout=15)
                data = response.json()
                
                if data.get('code') == 200:
                    stock_list = data.get('data', [])
                    for item in stock_list:
                        if item.get('vid') == vid:
                            stock_num = item.get('storageNum') or item.get('totalInventoryNum') or item.get('factoryInventoryNum') or 0
                            try:
                                total_stock = int(stock_num)
                                if total_stock > 0:
                                    print(f"✅ Stock found via stock/list: {total_stock}")
                                    return [{'stockNum': total_stock, 'warehouseCode': item.get('countryCode', 'CN')}]
                            except (ValueError, TypeError):
                                pass
            except Exception as e:
                print(f"⚠️ Error with stock/list: {e}")
        
        # ===== METHOD 4: Variant detail endpoint =====
        try:
            url = f"{self.BASE_URL}/product/variant/queryByVid"
            params = {"vid": vid}
            print(f"📡 Trying: {url}?vid={vid}")
            
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            data = response.json()
            
            if data.get('code') == 200:
                variant_data = data.get('data', {})
                if variant_data:
                    # Check for stock fields in the variant data
                    stock_fields = ['inventoryNum', 'stock', 'availableNum', 'quantity', 'listedNum']
                    for field in stock_fields:
                        if variant_data.get(field) is not None:
                            try:
                                stock_num = int(variant_data.get(field))
                                print(f"✅ Stock found in variant detail ({field}): {stock_num}")
                                return [{'stockNum': stock_num, 'warehouseCode': 'unknown'}]
                            except (ValueError, TypeError):
                                pass
        except Exception as e:
            print(f"⚠️ Error with variant/queryByVid: {e}")
        
        # ===== METHOD 5: Check product's listedNum as fallback =====
        if pid:
            try:
                url = f"{self.BASE_URL}/product/query"
                params = {"pid": pid}
                response = requests.get(url, headers=self.headers, params=params, timeout=15)
                data = response.json()
                
                if data.get('code') == 200:
                    product_data = data.get('data', {})
                    listed_num = product_data.get('listedNum')
                    if listed_num is not None:
                        try:
                            stock_num = int(listed_num)
                            if stock_num > 0:
                                print(f"✅ Stock from product.listedNum: {stock_num}")
                                return [{'stockNum': stock_num, 'warehouseCode': 'unknown'}]
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                print(f"⚠️ Error checking product.listedNum: {e}")
        
        # No stock found
        print(f"❌ No stock found for VID {vid} using any endpoint")
        return []


    def get_product_details(self, pid):
        """Get full product details including all variants"""
        url = f"{self.BASE_URL}/product/query"
        try:
            res = requests.get(url, headers=self.headers, params={"pid": pid}, timeout=30)
            data = res.json()
            
            print(f"Product details response code: {data.get('code')}")
            
            if data.get("code") == 200:
                prod = data.get("data", {})
                # Ensure images are clean
                if not prod.get('productImage') and prod.get('productImageList'):
                    prod['productImage'] = prod['productImageList'][0]
                return prod
            else:
                print(f"Product details error: {data.get('message')}")
                return None
        except Exception as e:
            print(f"Error getting product details: {e}")
            return None
    
    def get_variants(self, pid):
        """
        Fetches all variants for a product with full details.
        
        CJ API endpoint: /product/variant/queryByPid
        Returns: List of variant objects
        """
        url = f"{self.BASE_URL}/product/variant/queryByPid"
        
        # Try with page parameters to ensure we get all variants
        all_variants = []
        page_num = 1
        page_size = 100
        
        try:
            while True:
                params = {
                    "pid": pid,
                    "pageNumber": page_num,
                    "pageSize": page_size
                }
                
                print(f"Fetching variants page {page_num} for PID: {pid}")
                res = requests.get(url, headers=self.headers, params=params, timeout=30)
                data = res.json()
                
                print(f"Variants response code: {data.get('code')}")
                
                if data.get('code') == 200:
                    response_data = data.get('data', {})
                    
                    # Handle different response structures
                    if isinstance(response_data, dict):
                        variants = response_data.get('list', [])
                        if not variants:
                            variants = response_data.get('data', [])
                        if not variants:
                            # Some APIs return data directly
                            variants = [response_data] if response_data else []
                    elif isinstance(response_data, list):
                        variants = response_data
                    else:
                        variants = []
                    
                    if variants:
                        all_variants.extend(variants)
                        print(f"Found {len(variants)} variants on page {page_num}")
                        
                        # Check if there are more pages
                        total = response_data.get('total', 0) if isinstance(response_data, dict) else 0
                        if total > 0 and len(all_variants) >= total:
                            break
                        elif len(variants) < page_size:
                            break
                        else:
                            page_num += 1
                    else:
                        break
                else:
                    print(f"Variants API error: {data.get('message')}")
                    break
                    
        except Exception as e:
            print(f"Error getting variants for PID {pid}: {e}")
        
        print(f"Total variants found for PID {pid}: {len(all_variants)}")
        return all_variants
    
    def get_variant_details(self, vid):
        """Fetches the variant details (including variantKey) from CJ."""
        url = f"{self.BASE_URL}/product/variant/queryByVid"
        params = {"vid": vid}
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=20)
            data = response.json()
            if data.get('code') == 200:
                return data.get('data')
            return None
        except Exception as e:
            print(f"CJ API Error (queryByVid): {e}")
            return None
    
    def get_product_reviews(self, pid):
        """Fetches real customer reviews from CJ."""
        url = f"{self.BASE_URL}/product/comment/list"
        params = {"pid": pid, "pageNumber": 1, "pageSize": 20}
        try:
            res = requests.get(url, headers=self.headers, params=params, timeout=20)
            data = res.json()
            if data.get("code") == 200:
                return data.get("data", {}).get("list", [])
            return []
        except Exception:
            return []
    
    def get_variants_alternative(self, pid):
        """
        Alternative method to fetch variants using the product/query endpoint.
        Sometimes variants are nested in the product data.
        """
        url = f"{self.BASE_URL}/product/query"
        params = {"pid": pid}
        
        try:
            res = requests.get(url, headers=self.headers, params=params, timeout=30)
            data = res.json()
            
            if data.get('code') == 200:
                product_data = data.get('data', {})
                
                # Check if variants are directly in the product data
                if 'variants' in product_data:
                    variants = product_data.get('variants', [])
                    print(f"Found {len(variants)} variants in product data")
                    return variants
                
                # Check for variantList or similar
                if 'variantList' in product_data:
                    variants = product_data.get('variantList', [])
                    print(f"Found {len(variants)} variants in variantList")
                    return variants
                    
            return []
        except Exception as e:
            print(f"Error fetching variants via product query: {e}")
            return []


class CJManager:
    def __init__(self, token):
        self.base_url = "https://developers.cjdropshipping.com"
        self.headers = {
            "CJ-Access-Token": token,
            "platformToken": token,
            "Content-Type": "application/json"
        }
        self.service = CJService(token)

    def get_logistic_name(self, vid, country_code, zip_code, city, province):
        """
        Get shipping logistics name for a variant.
        """
        url = f"{self.base_url}/api2.0/v1/logistic/freightCalculate"
        
        payload = {
            "startCountryCode": "CN",
            "endCountryCode": country_code,
            "zip": zip_code,
            "province": province,
            "city": city,
            "products": [{"vid": vid, "quantity": 1}]
        }
        
        print(f"\n📦 Getting logistics for VID {vid}")
        print(f"   Country: {country_code}, City: {city}")
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=20)
            data = response.json()
            
            if data.get('code') == 200 and data.get('data'):
                logistic_name = data['data'][0].get('logisticName')
                print(f"   ✅ Logistics: {logistic_name}")
                return logistic_name
            else:
                print(f"   ⚠️ No logistics found: {data.get('message')}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"   ⚠️ Timeout getting logistics")
            return None
            
        except Exception as e:
            print(f"   ⚠️ Error getting logistics: {e}")
            return None


    def create_cj_order_multiple(self, order_info, logistic_name, products_data):
        """
        Create a CJ order with multiple products.
        This is called by fulfill_cj_order_corrected.
        """
        url = f"{self.base_url}/api2.0/v1/shopping/order/createOrderV2"
        
        payload = {
            "orderNumber": f"{order_info['number']}-{int(time.time())}",
            "shippingZip": str(order_info['zip']),
            "shippingCountryCode": str(order_info['country_code']),
            "shippingCountry": str(order_info['country_name']),
            "countryCode": str(order_info['country_code']),
            "shippingProvince": str(order_info['province']),
            "shippingCity": str(order_info['city']),
            "shippingAddress": str(order_info['address']),
            "shippingCustomerName": str(order_info['name']),
            "shippingPhone": str(order_info['phone']),
            "logisticName": logistic_name,
            "payType": 3,  # Prepaid
            "fromCountryCode": "CN",
            "products": products_data
        }
        
        print(f"\n📤 Sending order to CJ:")
        print(f"   URL: {url}")
        print(f"   Order Number: {payload['orderNumber']}")
        print(f"   Products: {len(payload['products'])}")
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            print(f"   Response Status: {response.status_code}")
            
            result = response.json()
            print(f"   Response Code: {result.get('code')}")
            
            if result.get('code') != 200:
                print(f"   Response Message: {result.get('message')}")
            
            return result
            
        except requests.exceptions.Timeout:
            print(f"❌ Timeout creating CJ order")
            return {"code": 408, "message": "Request timeout"}
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error creating CJ order: {e}")
            return {"code": 500, "message": str(e)}
            
        except Exception as e:
            print(f"❌ Unexpected error creating CJ order: {e}")
            return {"code": 500, "message": str(e)}
        
    def fulfill_cj_order_corrected(self, order):
        """
        Create a CJ order with all items.
        Supports:
        - Regular products with direct CJ VID
        - Products with variants (finds CJ VID from variants)
        - Grouped products (finds CJ VID from their variants)
        - Products with CJProduct records
        - Combines quantities for duplicate VIDs
        """
        products_data = []
        fulfillment_errors = []
        processed_vids = set()
        
        print(f"\n{'='*60}")
        print(f"🔄 Fulfilling CJ Order: {order.order_number}")
        print(f"   Order ID: {order.id}")
        print(f"   Items: {order.items.count()}")
        print(f"   Customer: {order.customer_name}")
        print(f"{'='*60}")
        
        for idx, item in enumerate(order.items.all(), 1):
            cj_vid = None
            product = item.product
            variant = item.variant
            
            print(f"\n📦 Item {idx}: {product.title}")
            print(f"   Quantity: {item.quantity}")
            
            # ============================================================
            # METHOD 1: Direct CJ VID from the product
            # ============================================================
            if product.cj_vid:
                cj_vid = product.cj_vid
                print(f"   ✅ Direct CJ VID from product: {cj_vid}")
            
            # ============================================================
            # METHOD 2: CJ VID from the item's variant
            # ============================================================
            if not cj_vid and variant and variant.cj_vid:
                cj_vid = variant.cj_vid
                print(f"   ✅ CJ VID from cart variant: {cj_vid}")
            
            # ============================================================
            # METHOD 3: Find CJ VID from product's variants
            # ============================================================
            if not cj_vid:
                variant_with_cj = product.variants.filter(cj_vid__isnull=False).first()
                if variant_with_cj:
                    cj_vid = variant_with_cj.cj_vid
                    print(f"   ✅ CJ VID from product variant {variant_with_cj.id}: {cj_vid}")
            
            # ============================================================
            # METHOD 4: Grouped product - find CJ VID from its variants
            # ============================================================
            if not cj_vid:
                try:
                    from builder.models import GroupedProduct
                    grouped = GroupedProduct.objects.filter(product=product).first()
                    if grouped:
                        print(f"   🔍 Found grouped product: {grouped.group_display_name}")
                        print(f"   🔍 Variant IDs in group: {grouped.variant_ids}")
                        
                        # Get variants in this group
                        variants_in_group = ProductVariant.objects.filter(
                            id__in=grouped.variant_ids,
                            cj_vid__isnull=False
                        )
                        
                        # Try to get the specific variant if we have selected options
                        selected_options = {}
                        if hasattr(item, 'selected_options') and item.selected_options:
                            selected_options = item.selected_options
                            print(f"   🔍 Selected options: {selected_options}")
                            
                            # Try to match exact variant by options
                            for v in variants_in_group:
                                match = True
                                for key, value in selected_options.items():
                                    if v.options.get(key) != value:
                                        match = False
                                        break
                                if match and v.cj_vid:
                                    cj_vid = v.cj_vid
                                    print(f"   ✅ Matched variant by options: {v.id} -> {cj_vid}")
                                    break
                        
                        # If still no match, use the first variant with CJ VID
                        if not cj_vid:
                            first_variant = variants_in_group.first()
                            if first_variant and first_variant.cj_vid:
                                cj_vid = first_variant.cj_vid
                                print(f"   ✅ First variant with CJ VID: {first_variant.id} -> {cj_vid}")
                except Exception as e:
                    print(f"   ⚠️ Error checking grouped product: {e}")
            
            # ============================================================
            # METHOD 5: CJProduct record (legacy/fallback)
            # ============================================================
            if not cj_vid:
                try:
                    from builder.models import CJProduct
                    cj_product = CJProduct.objects.get(
                        page=order.page,
                        local_product=product
                    )
                    if cj_product.cj_variant_id:
                        cj_vid = cj_product.cj_variant_id
                        print(f"   ✅ CJ VID from CJProduct: {cj_vid}")
                except CJProduct.DoesNotExist:
                    pass
                except Exception as e:
                    print(f"   ⚠️ Error checking CJProduct: {e}")
            
            # ============================================================
            # METHOD 6: Try to find any variant with CJ VID (last resort)
            # ============================================================
            if not cj_vid:
                any_variant = product.variants.filter(cj_vid__isnull=False).first()
                if any_variant:
                    cj_vid = any_variant.cj_vid
                    print(f"   ✅ Last resort - found CJ VID in variant {any_variant.id}: {cj_vid}")
            
            # ============================================================
            # Add to products_data if we found a VID
            # ============================================================
            if cj_vid:
                # Check if this VID already exists (combine quantities)
                existing = None
                for p in products_data:
                    if p.get('vid') == cj_vid:
                        existing = p
                        break
                
                if existing:
                    existing['quantity'] += item.quantity
                    print(f"   📦 Combined quantity for VID {cj_vid}: {existing['quantity']}")
                else:
                    products_data.append({
                        "vid": cj_vid,
                        "quantity": item.quantity
                    })
                    processed_vids.add(cj_vid)
                    print(f"   📦 Added product: VID {cj_vid}, Qty: {item.quantity}")
            else:
                error_msg = f"No CJ VID found for product: {product.title} (ID: {product.id})"
                print(f"   ❌ {error_msg}")
                fulfillment_errors.append({
                    'item_id': item.id,
                    'product_id': product.id,
                    'product_title': product.title,
                    'variant_id': variant.id if variant else None,
                    'error': error_msg
                })
        
        # ============================================================
        # Check if we have any products to fulfill
        # ============================================================
        print(f"\n{'='*60}")
        print(f"📊 Fulfillment Summary:")
        print(f"   Total items processed: {order.items.count()}")
        print(f"   Products with CJ VID: {len(products_data)}")
        print(f"   Errors: {len(fulfillment_errors)}")
        print(f"{'='*60}")
        
        if not products_data:
            print("❌ No valid CJ VIDs found in order items")
            
            # Create sync log for failure
            try:
                from builder.models import CJSyncLog
                CJSyncLog.objects.create(
                    page=order.page,
                    sync_type='order_submit',
                    status='failed',
                    error_message='No valid CJ VIDs found',
                    error_details={'errors': fulfillment_errors},
                    started_at=timezone.now(),
                    completed_at=timezone.now()
                )
            except Exception as e:
                print(f"⚠️ Could not create sync log: {e}")
            
            return False
        
        # ============================================================
        # Get logistics for the FIRST product
        # ============================================================
        first_vid = products_data[0]['vid']
        print(f"\n📦 Getting logistics for first product VID: {first_vid}")
        
        logistic_name = self.get_logistic_name(
            vid=first_vid,
            country_code=order.country_iso,
            zip_code=order.delivery_zip,
            city=order.delivery_city,
            province=order.delivery_state
        )
        
        if not logistic_name:
            logistic_name = "CJPacket Sensitive"
            print(f"⚠️ Using default logistics: {logistic_name}")
        else:
            print(f"✅ Logistics: {logistic_name}")
        
        # ============================================================
        # Prepare order info
        # ============================================================
        order_info = {
            "number": order.order_number,
            "zip": order.delivery_zip,
            "country_code": order.country_iso,
            "country_name": order.customer_country,
            "province": order.delivery_state,
            "city": order.delivery_city,
            "address": order.delivery_address,
            "name": order.customer_name,
            "phone": order.phone,
        }
        
        print(f"\n📤 Creating CJ order with {len(products_data)} products")
        print(f"   Products: {products_data}")
        
        # ============================================================
        # Create the order on CJ
        # ============================================================
        result = self.create_cj_order_multiple(order_info, logistic_name, products_data)
        
        # ============================================================
        # Process the result
        # ============================================================
        if result.get('code') == 200:
            cj_order_id = result['data'].get('orderId')
            print(f"\n✅ CJ Order created successfully!")
            print(f"   CJ Order ID: {cj_order_id}")
            
            # Update the local order
            order.cj_order_id = cj_order_id
            order.cj_fulfilled_at = timezone.now()
            order.status = 'fulfilled'
            order.save()
            
            # Create success log
            try:
                from builder.models import CJSyncLog
                CJSyncLog.objects.create(
                    page=order.page,
                    sync_type='order_submit',
                    status='success',
                    items_processed=len(products_data),
                    items_succeeded=len(products_data),
                    items_failed=len(fulfillment_errors),
                    api_calls_made=1,
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    response_data={
                        'order_id': cj_order_id,
                        'products': products_data,
                        'logistics': logistic_name
                    }
                )
                print(f"   📝 Sync log created")
            except Exception as e:
                print(f"⚠️ Could not create sync log: {e}")
            
            return True
            
        else:
            # Failed
            error_msg = result.get('message', 'Unknown error')
            error_code = result.get('code', 'Unknown')
            print(f"\n❌ Failed to create CJ order!")
            print(f"   Error Code: {error_code}")
            print(f"   Error Message: {error_msg}")
            print(f"   Full Response: {result}")
            
            # Create failure log
            try:
                from builder.models import CJSyncLog
                CJSyncLog.objects.create(
                    page=order.page,
                    sync_type='order_submit',
                    status='failed',
                    error_message=error_msg,
                    error_details={
                        'code': error_code,
                        'result': result,
                        'products': products_data,
                        'fulfillment_errors': fulfillment_errors
                    },
                    started_at=timezone.now(),
                    completed_at=timezone.now()
                )
                print(f"   📝 Error log created")
            except Exception as e:
                print(f"⚠️ Could not create error log: {e}")
            
            return False

    # ============================================================
    # ===== FIXED: PROPER COLOR/SIZE EXTRACTION =====
    # ============================================================
    
    def _extract_color_size(self, variant_key):
        """
        Extract color and size from CJ variantKey string.
        
        Handles formats like:
        - "Black Zone2-S" -> color: "Black Zone2", size: "S"
        - "Black Zone8 Set-2XL" -> color: "Black Zone8 Set", size: "2XL"
        - "Color:Black-Size:S" -> color: "Black", size: "S"
        - "Color:Black,Size:S" -> color: "Black", size: "S"
        - "Black Zone2-S-XL" -> color: "Black Zone2", size: "S-XL" (rare)
        """
        color_value = None
        size_value = None
        
        if not variant_key:
            return color_value, size_value
        
        # ===== METHOD 1: Check for "Color:" and "Size:" format =====
        if 'Color:' in variant_key or 'Size:' in variant_key:
            parts = variant_key.split('-')
            for part in parts:
                if 'Color:' in part:
                    color_value = part.split('Color:', 1)[1].strip()
                elif 'Size:' in part:
                    size_value = part.split('Size:', 1)[1].strip()
            
            # Also check comma format
            if not color_value or not size_value:
                for part in parts:
                    if 'Color,' in part:
                        color_value = part.split('Color,', 1)[1].strip()
                    elif 'Size,' in part:
                        size_value = part.split('Size,', 1)[1].strip()
            
            return color_value, size_value
        
        # ===== METHOD 2: Last hyphen separates color and size =====
        # Find the LAST hyphen to split (handles names with hyphens like "Zone2")
        last_hyphen = variant_key.rfind('-')
        if last_hyphen > 0:
            # Split at the LAST hyphen
            color_value = variant_key[:last_hyphen].strip()
            size_value = variant_key[last_hyphen + 1:].strip()
            
            # Clean up - if size still has hyphens, it might be part of color
            if size_value and '-' in size_value:
                # Try to find where size typically starts (S, M, L, XL, etc.)
                size_patterns = ['S-', 'M-', 'L-', 'XL-', 'XXL-', 'XXXL-', '2XL-', '3XL-', '4XL-', '5XL-', '6XL-', '7XL-', '8XL-']
                found = False
                for pattern in size_patterns:
                    if pattern in variant_key:
                        # Find the position of the pattern
                        pos = variant_key.find(pattern)
                        if pos > 0:
                            color_value = variant_key[:pos].strip()
                            size_value = variant_key[pos:].strip()
                            found = True
                            break
                
                # If not found with patterns, keep the last part as size
                if not found:
                    parts = variant_key.split('-')
                    # Usually size is the last part for common formats
                    if len(parts) >= 2:
                        color_value = '-'.join(parts[:-1]).strip()
                        size_value = parts[-1].strip()
            
            return color_value, size_value
        
        # ===== METHOD 3: Check for common size patterns at the end =====
        # Look for size patterns without a hyphen
        size_patterns = [' S', ' M', ' L', ' XL', ' XXL', ' XXXL', ' 2XL', ' 3XL', ' 4XL', ' 5XL', ' 6XL']
        for pattern in size_patterns:
            if variant_key.endswith(pattern):
                color_value = variant_key[:-len(pattern)].strip()
                size_value = pattern.strip()
                return color_value, size_value
        
        # ===== METHOD 4: Fallback - return the whole key as color =====
        return variant_key, None
    
    def _parse_variant_price(self, variant_data):
        """Safely parse variant price from CJ data."""
        price = variant_data.get('variantSellPrice')
        if price is None:
            price = variant_data.get('variantPrice')
        if price is None:
            price = 0
        try:
            return float(price)
        except (ValueError, TypeError):
            return 0.0

    def _create_or_update_variant(self, product_obj, vid, variant_data, color=None, size=None):
        """
        Create or update a ProductVariant with CJ data.
        Now uses the improved get_stock_by_vid with fallbacks.
        """
        from builder.models import ProductVariant, ProductInventory
        import requests
        from django.core.files.base import ContentFile
        import io
        from PIL import Image
        
        variant_sku = variant_data.get('variantSku', '')
        variant_price = self._parse_variant_price(variant_data)
        variant_image_url = variant_data.get('variantImage', '')
        
        # ===== GET STOCK USING IMPROVED METHOD =====
        total_stock = 0
        pid = product_obj.cj_pid
        
        # Try to get stock using the improved method
        try:
            stock_data = self.service.get_stock_by_vid(vid, pid)
            if stock_data:
                total_stock = sum(int(item.get('stockNum', 0)) for item in stock_data)
                print(f"📦 Stock from API for {vid}: {total_stock}")
        except Exception as e:
            print(f"⚠️ Error getting stock for vid {vid}: {e}")
        
        # Fallback 1: use inventoryNum from variant data
        if total_stock == 0:
            inventory_num = variant_data.get('inventoryNum')
            if inventory_num is not None:
                try:
                    total_stock = int(inventory_num)
                    print(f"📦 Stock from inventoryNum for {vid}: {total_stock}")
                except (ValueError, TypeError):
                    total_stock = 0
        
        # Fallback 2: use listedNum (with caution)
        if total_stock == 0:
            listed_num = variant_data.get('listedNum')
            if listed_num is not None:
                try:
                    # If listedNum is small (1-10), it might be MOQ, not stock
                    # But we'll use it as stock anyway since we have nothing else
                    total_stock = int(listed_num)
                    print(f"📦 Stock from listedNum for {vid}: {total_stock} (using as fallback)")
                except (ValueError, TypeError):
                    total_stock = 0
        
        # Fallback 3: check if product is active and set default stock
        if total_stock == 0 and product_obj.status == 'active':
            total_stock = 10  # Default stock for active products
            print(f"📦 Using default stock (10) for {vid} (product is active)")
        
        print(f"📊 Final stock for variant {vid}: {total_stock}")
        
        # ===== BUILD OPTIONS DICT =====
        options = {}
        if color:
            options['Color'] = color
        if size:
            options['Size'] = size
        
        # Determine SKU
        sku = variant_sku
        if not sku:
            sku = f"VAR-{vid}"
        
        # ===== CREATE OR UPDATE VARIANT =====
        variant, created = ProductVariant.objects.update_or_create(
            sku=sku,
            defaults={
                'product': product_obj,
                'cj_vid': vid,
                'options': options,
                'option1': size or '',
                'option2': color or '',
                'price': Decimal(str(variant_price)) if variant_price else Decimal('0.00'),
                'compare_at_price': product_obj.compare_at_price,
                'quantity': total_stock,
                'track_quantity': True,
                'low_stock_threshold': 5,
                'barcode': variant_data.get('barcode', ''),
            }
        )
        
        # ===== HANDLE VARIANT IMAGE =====
        if variant_image_url:
            try:
                # Clean up URL
                if not variant_image_url.startswith('http'):
                    if variant_image_url.startswith('//'):
                        variant_image_url = 'https:' + variant_image_url
                    else:
                        variant_image_url = 'https://' + variant_image_url
                
                # Download image
                response = requests.get(variant_image_url, timeout=15, stream=True)
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '')
                    if content_type.startswith('image/'):
                        content = response.content
                        
                        # Compress if too large (max 5MB for variant images)
                        max_bytes = 5 * 1024 * 1024
                        if len(content) > max_bytes:
                            try:
                                img = Image.open(io.BytesIO(content))
                                
                                # Convert to RGB if necessary
                                if img.mode in ('RGBA', 'LA', 'P'):
                                    background = Image.new('RGB', img.size, (255, 255, 255))
                                    if img.mode == 'P':
                                        img = img.convert('RGBA')
                                    if img.mode == 'RGBA':
                                        background.paste(img, mask=img.split()[-1])
                                    else:
                                        background.paste(img)
                                    img = background
                                elif img.mode != 'RGB':
                                    img = img.convert('RGB')
                                
                                # Compress
                                quality = 85
                                output = io.BytesIO()
                                img.save(output, format='JPEG', quality=quality, optimize=True)
                                compressed_size = len(output.getvalue())
                                
                                while compressed_size > max_bytes and quality > 20:
                                    quality -= 10
                                    output = io.BytesIO()
                                    img.save(output, format='JPEG', quality=quality, optimize=True)
                                    compressed_size = len(output.getvalue())
                                
                                content = output.getvalue()
                                print(f"✅ Compressed variant image: {len(content)/1024/1024:.1f}MB")
                            except Exception as e:
                                print(f"⚠️ Error compressing variant image: {e}")
                        
                        # Generate filename
                        filename = variant_image_url.split('/')[-1].split('?')[0]
                        if not filename or '.' not in filename:
                            filename = f"variant_{vid}.jpg"
                        elif not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                            filename = filename.split('.')[0] + '.jpg'
                        
                        # Save the image
                        variant.image.save(filename, ContentFile(content), save=True)
                        print(f"✅ Saved variant image for {vid}")
            except Exception as e:
                print(f"⚠️ Failed to save variant image for {vid}: {e}")
        
        # ===== CREATE OR UPDATE INVENTORY =====
        inventory, _ = ProductInventory.objects.update_or_create(
            sku=sku,
            defaults={
                'quantity': total_stock,
                'track_quantity': True,
                'low_stock_threshold': 5,
                'allow_backorders': False,
            }
        )
        
        variant.inventory = inventory
        variant.save()
        
        print(f"✅ Variant {vid}: stock={total_stock}, sku={sku}")
        
        return variant, created

    
    
    # ============================================================
    # ===== MAIN METHOD: SYNC ALL VARIANTS =====
    # ============================================================
    
    def sync_all_variants(self, product_obj, variants_data=None):
        """
        Sync ALL CJ variants for a product to your ProductVariant model.
        Uses the improved stock fetching with fallbacks.
        """
        from builder.models import ProductVariant
        
        stats = {
            'total': 0,
            'created': 0,
            'updated': 0,
            'failed': 0,
            'variants': []
        }
        
        if not product_obj.cj_pid:
            print("No CJ PID found for this product")
            stats['error'] = 'No CJ PID'
            return stats
        
        # Get variants from CJ if not provided
        if variants_data is None:
            variants_data = self.service.get_variants(product_obj.cj_pid)
        
        if not variants_data:
            variants_data = self.service.get_variants_alternative(product_obj.cj_pid)
        
        if not variants_data:
            print(f"No variants found for PID: {product_obj.cj_pid}")
            stats['error'] = 'No variants found'
            return stats
        
        print(f"Found {len(variants_data)} variants for PID: {product_obj.cj_pid}")
        stats['total'] = len(variants_data)
        
        # Delete existing variants for this product
        ProductVariant.objects.filter(product=product_obj).delete()
        
        colors = set()
        sizes = set()
        total_stock = 0
        
        for variant_data in variants_data:
            try:
                vid = variant_data.get('vid')
                if not vid:
                    stats['failed'] += 1
                    continue
                
                # Extract color and size
                variant_key = variant_data.get('variantKey', '')
                color_value, size_value = self._extract_color_size(variant_key)
                
                if color_value:
                    colors.add(color_value)
                if size_value:
                    sizes.add(size_value)
                
                # Create variant with stock (using improved method)
                variant, created = self._create_or_update_variant(
                    product_obj=product_obj,
                    vid=vid,
                    variant_data=variant_data,
                    color=color_value,
                    size=size_value
                )
                
                total_stock += variant.quantity
                
                if created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1
                
                stats['variants'].append({
                    'vid': vid,
                    'created': created,
                    'color': color_value,
                    'size': size_value,
                    'sku': variant_data.get('variantSku', ''),
                    'price': variant_data.get('variantSellPrice'),
                    'stock': variant.quantity,
                    'has_image': bool(variant_data.get('variantImage'))
                })
                
                print(f"✅ Variant {vid}: {variant_key} -> Stock: {variant.quantity}")
                
            except Exception as e:
                print(f"Error syncing variant {variant_data.get('vid')}: {e}")
                stats['failed'] += 1
        
        # Update product with colors, sizes, and total stock
        if colors:
            product_obj.colors = ', '.join(sorted(colors))
        if sizes:
            product_obj.sizes = ', '.join(sorted(sizes))
        
        product_obj.has_variants = len(variants_data) > 1
        product_obj.quantity = total_stock
        product_obj.save()
        
        print(f"✅ Variant sync complete: {stats['created']} created, {stats['updated']} updated, {stats['failed']} failed")
        print(f"📊 Total stock: {total_stock}")
        
        return stats

    # ============================================================
    # ===== SINGLE VARIANT SYNC (for updating a single variant) =====
    # ============================================================
    
    def sync_single_variant(self, product_obj, vid):
        """
        Sync a single variant from CJ to your ProductVariant model.
        
        Args:
            product_obj: Your local Product instance
            vid: The CJ variant ID to sync
        
        Returns:
            dict: Statistics about the synced variant
        """
        stats = {
            'success': False,
            'vid': vid,
            'created': False,
            'updated': False,
            'error': None
        }
        
        try:
            # Get variant details from CJ
            variant_data = self.service.get_variant_details(vid)
            
            if not variant_data:
                stats['error'] = 'Variant not found in CJ'
                return stats
            
            # Extract color and size
            variant_key = variant_data.get('variantKey', '')
            color_value, size_value = self._extract_color_size(variant_key)
            
            # Create or update variant
            variant, created = self._create_or_update_variant(
                product_obj=product_obj,
                vid=vid,
                variant_data=variant_data,
                color=color_value,
                size=size_value
            )
            
            stats['success'] = True
            stats['created'] = created
            stats['updated'] = not created
            stats['variant'] = {
                'id': variant.id,
                'sku': variant.sku,
                'color': color_value,
                'size': size_value,
                'price': float(variant.price) if variant.price else 0,
                'quantity': variant.quantity
            }
            
            # Update product colors/sizes if needed
            if color_value:
                existing_colors = set(product_obj.colors.split(', ')) if product_obj.colors else set()
                existing_colors.add(color_value)
                product_obj.colors = ', '.join(sorted(existing_colors))
            
            if size_value:
                existing_sizes = set(product_obj.sizes.split(', ')) if product_obj.sizes else set()
                existing_sizes.add(size_value)
                product_obj.sizes = ', '.join(sorted(existing_sizes))
            
            product_obj.save()
            
            print(f"✅ Synced single variant: {variant_key} -> Color: {color_value}, Size: {size_value}")
            
        except Exception as e:
            stats['error'] = str(e)
            print(f"Error syncing variant {vid}: {e}")
        
        return stats

    # ============================================================
    # ===== LEGACY METHOD (kept for compatibility) =====
    # ============================================================
    
    def sync_product_color_size(self, product_obj):
        """
        DEPRECATED: Use sync_all_variants instead.
        This is kept for backwards compatibility.
        """
        print("⚠️ sync_product_color_size is deprecated. Use sync_all_variants instead.")
        return self.sync_all_variants(product_obj)

# #         # http://localhost:8000/builder/cj-search/lux1/?q=phone