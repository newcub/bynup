import os
import re
from pathlib import Path

# ============================================
# CONFIGURATION
# ============================================

TEMPLATES_DIR = 'templates/builder/public_templates'
DEFAULT_IMAGE = "https://images.pexels.com/photos/6311675/pexels-photo-6311675.jpeg?auto=compress&cs=tinysrgb&w=800"

# ============================================
# THE REPLACEMENT TEMPLATE
# ============================================

def generate_replacement(element_id, alt_text='Image', default_image=DEFAULT_IMAGE):
    """Generate the replacement HTML for an element ID"""
    return f'''{{% with video=video_customizations.{element_id} %}}
    {{% if video %}}
        {{# ===== VIDEO EXISTS - RENDER VIDEO ===== #}}
        <div class="editable-video" 
             data-image="{element_id}" 
             data-is-video="true"
             style="position: relative; overflow: hidden; display: inline-block; max-width: 100%; border-radius: 8px; cursor: pointer;">
            
            <video 
                src="{{{{ video.video_url }}}}" 
                poster="{{{{ video.poster_url|default:'' }}}}"
                {{% if video.autoplay %}}autoplay{{% endif %}}
                {{% if video.loop %}}loop{{% endif %}}
                {{% if video.muted %}}muted{{% endif %}}
                {{% if video.controls %}}controls{{% endif %}}
                style="width: 100%; height: 100%; display: block; object-fit: cover;"
            >
                Your browser does not support the video tag.
            </video>
            
            {{# ===== PLAY BUTTON OVERLAY ===== #}}
            {{% if video.show_play_button %}}
            <div class="video-overlay" style="
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: rgba(0, 0, 0, 0.6);
                border-radius: 50%;
                width: 60px;
                height: 60px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 24px;
                pointer-events: none;
                transition: all 0.3s ease;
                opacity: 0.7;
            ">
                <i class="fas fa-play"></i>
            </div>
            {{% endif %}}
        </div>
        
    {{% else %}}
        {{# ===== NO VIDEO - RENDER IMAGE ===== #}}
        {{% if image_customizations.{element_id} %}}
            <img src="{{{{ image_customizations.{element_id}.image_url }}}}" 
                 alt="{{{{ image_customizations.{element_id}.alt_text|default:'{alt_text}' }}}}" 
                 class="editable-image" 
                 data-image="{element_id}">
        {{% else %}}
            <img src="{default_image}" 
                 alt="{alt_text}" 
                 class="editable-image" 
                 data-image="{element_id}">
        {{% endif %}}
    {{% endif %}}
{{% endwith %}}'''


# ============================================
# HELPER FUNCTIONS
# ============================================

def find_image_customizations(content):
    """Find all image_customizations patterns in the content"""
    # Find all occurrences of image_customizations.XXX.
    pattern = r'image_customizations\.(\d+)\.'
    matches = re.findall(pattern, content)
    return list(set(matches))  # Remove duplicates


def find_img_tag_for_element(content, element_id):
    """Find the complete img tag for a given element ID"""
    # Look for img tag with data-image="element_id"
    patterns = [
        rf'<img[^>]*data-image=["\']{element_id}["\'][^>]*>',
        rf'<img[^>]*src=["\'][^"\']*["\'][^>]*data-image=["\']{element_id}["\'][^>]*>',
        rf'<img[^>]*class=["\'][^"\']*editable-image[^"\']*["\'][^>]*data-image=["\']{element_id}["\'][^>]*>',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(0)
    
    return None


def extract_alt_text(content, element_id):
    """Extract alt text for an element"""
    # Look for alt attribute in the img tag
    patterns = [
        rf'alt=["\']([^"\']*)["\']',
        rf'alt="{{{{[^}}]*{element_id}[^}}]*default:[\'\"]([^\'\"]+)[\'\"]}}}}',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    
    return 'Image'


def extract_default_image(content, element_id):
    """Extract the default image URL for an element"""
    # Look for a default image URL in the img tag
    pattern = rf'<img[^>]*src=["\']([^"\']*\.(?:jpg|jpeg|png|gif|webp|svg))["\'][^>]*data-image=["\']{element_id}["\']'
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Try the other way around
    pattern = rf'<img[^>]*data-image=["\']{element_id}["\'][^>]*src=["\']([^"\']*\.(?:jpg|jpeg|png|gif|webp|svg))["\']'
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return DEFAULT_IMAGE


# ============================================
# MAIN FUNCTION
# ============================================

def update_templates(templates_dir=TEMPLATES_DIR, dry_run=True):
    """
    Update all public templates with the new image/video format.
    """
    
    if not os.path.exists(templates_dir):
        print(f"❌ ERROR: Directory not found: {templates_dir}")
        return
    
    # Get all HTML files
    template_files = []
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                template_files.append(os.path.join(root, file))
    
    print(f"📁 Found {len(template_files)} template files in: {templates_dir}")
    print("=" * 60)
    
    if len(template_files) == 0:
        print("⚠️ No HTML files found.")
        return
    
    total_replacements = 0
    files_modified = 0
    all_element_ids = []
    
    for file_path in template_files:
        print(f"\n📄 Processing: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all image_customizations patterns
        element_ids = find_image_customizations(content)
        
        if not element_ids:
            print(f"   ℹ️ No image_customizations found")
            continue
        
        print(f"   🔍 Found {len(element_ids)} image customization(s): {element_ids}")
        all_element_ids.extend(element_ids)
        
        new_content = content
        replacements_made = 0
        
        for element_id in element_ids:
            # Check if this element already has video support
            if f'video_customizations.{element_id}' in content:
                print(f"   ⏭️ Element {element_id} already has video support")
                continue
            
            # Find the img tag
            img_tag = find_img_tag_for_element(content, element_id)
            
            if img_tag:
                alt_text = extract_alt_text(img_tag, element_id)
                default_img = extract_default_image(img_tag, element_id)
                
                # Generate replacement
                replacement = generate_replacement(element_id, alt_text, default_img)
                
                # Replace the img tag
                escaped_old = re.escape(img_tag)
                new_content = re.sub(escaped_old, replacement, new_content, flags=re.DOTALL)
                
                replacements_made += 1
                print(f"   ✅ Element {element_id} replaced")
            else:
                # Try to find and replace just the src pattern
                print(f"   ⚠️ Could not find img tag for element {element_id}, looking for src pattern...")
                
                # Look for src="{{ image_customizations.XXX.image_url }}"
                src_pattern = rf'src=["\']{{{{\s*image_customizations\.{element_id}\.image_url\s*}}}}["\']'
                src_match = re.search(src_pattern, content)
                
                if src_match:
                    alt_text = extract_alt_text(content, element_id)
                    default_img = extract_default_image(content, element_id)
                    replacement = generate_replacement(element_id, alt_text, default_img)
                    
                    # Replace just the src pattern (not ideal, but better than nothing)
                    escaped_old = re.escape(src_match.group(0))
                    new_content = re.sub(escaped_old, replacement, new_content, flags=re.DOTALL)
                    
                    replacements_made += 1
                    print(f"   ✅ Element {element_id} replaced (src pattern only)")
                else:
                    print(f"   ❌ Could not find src pattern for element {element_id}")
        
        if replacements_made > 0:
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"   💾 Saved: {file_path}")
                files_modified += 1
            else:
                print(f"   🔄 DRY RUN: Would save {file_path}")
                files_modified += 1
            
            total_replacements += replacements_made
    
    print("\n" + "=" * 60)
    print(f"📊 SUMMARY:")
    print(f"   Total files processed: {len(template_files)}")
    print(f"   Files modified: {files_modified}")
    print(f"   Total replacements: {total_replacements}")
    print(f"   Unique element IDs found: {len(set(all_element_ids))}")
    if all_element_ids:
        print(f"   Element IDs: {sorted(set(all_element_ids))}")
    print(f"   Mode: {'DRY RUN (no changes saved)' if dry_run else 'LIVE (changes saved)'}")
    
    if dry_run:
        print("\n⚠️ This was a DRY RUN. To apply changes, run with dry_run=False")


# ============================================
# RUN THE SCRIPT
# ============================================

if __name__ == '__main__':
    # First, run a dry run to see what will change
    print("🔍 RUNNING DRY RUN...\n")
    update_templates(dry_run=True)
    
    # Ask for confirmation before applying
    print("\n" + "=" * 60)
    response = input("Do you want to apply these changes? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        print("\n🚀 APPLYING CHANGES...\n")
        update_templates(dry_run=False)
        print("\n✅ All templates updated successfully!")
    else:
        print("\n❌ Changes cancelled. No files were modified.")