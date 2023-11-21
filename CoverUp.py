#!/usr/bin/env python3
# This is OSS licensed under GPLV3.0
# (c) 2023 Björn Seipel

import PySimpleGUI as sg
import pypdfium2 as pdfium
import io, os, sys, re
from PIL import Image, ImageTk, ImageDraw, ImageFont
from fpdf import FPDF
from collections import deque
from copy import deepcopy
from datetime import datetime
from multiprocessing import freeze_support

class ImageContainer:
    '''Container for images of PDF pages'''
    zoom_factor = 100
    
    def __init__(self, image, size=(0,0),  delta_x=0, delta_y=0):
        self.image=image
        self.size = size 
        self.height_in_pt = size[0]
        self.width_in_pt = size[1]
        self.delta_x = delta_x
        self.delta_y = delta_y
        self.scaled_image = self.image
        self.id = None
        self.rectangles = deque(())
               
    def increase_zoom(self, number=20):
        '''Zoom in image. Returns new zoom_factor'''
        ImageContainer.zoom_factor += number
        if ImageContainer.zoom_factor > 240:
            ImageContainer.zoom_factor = 240
        else:
            self.scale_image()     
        return [ImageContainer.zoom_factor] 
               
    def decrease_zoom(self, number=20):
        '''Zoom out of image. Returns new zoom_factor''' 
        ImageContainer.zoom_factor -= number
        if ImageContainer.zoom_factor < 20:
            ImageContainer.zoom_factor = 20
        else:self.scale_image()
        return [ImageContainer.zoom_factor]
      
    def scale_image(self):
        '''Scale original size image for display in Graph element.'''
        width, height = self.image.size
        newwidth = int(width * ImageContainer.zoom_factor / 100)
        newheight = int(height * ImageContainer.zoom_factor / 100)
        self.scaled_image = self.image.resize((newwidth, newheight), resample=Image.LANCZOS)
    
    def undo(self):
        '''Go back in history. Remove last rectangle and redraw rectangles.'''
        if len(self.rectangles)>0:           
            delete_id=self.rectangles.pop()
            window['-GRAPH-'].delete_figure(delete_id[3])  
        return self
     
    def data(self):
        '''Return bytes of scaled image.'''
        with io.BytesIO() as output:
            self.scaled_image.save(output, format='PNG')
            data = output.getvalue()
            self.datacache = data
            
            return data    
       
    def jpg(self, image=None, image_quality=85, scale=1):
        '''Return bytes of compressed image'''
        with io.BytesIO() as output:
            image_to_save = image if scale==1 else image.resize((int(image.width * scale), int(image.height * scale)), resample=Image.LANCZOS) 
            image_to_save.save(output, format='JPEG', quality=image_quality, optimize=True)
            data = output.getvalue()
        return data
        
    def refresh(self):
        '''Update the scaled image and return self'''
        self.scale_image()
        return self
    
    def finalized_image (self, format='PIL', image_quality=100, scale=1):
        '''Return a copy of the imported image with all the rectangles and in the requested format.'''
        final_image = self.draw_rectangles_on_image(self.image.copy())
        if format in ('JPEG','JPG'):
            return self.jpg(final_image.convert('RGB'), image_quality, scale)
        else:
            return final_image
    
    def draw_rectangles_on_image(self, image):
        '''Draw the rectangles in self.rectangles on image'''
        draw = ImageDraw.Draw(image)
        for rectangle in self.rectangles:
            draw.rectangle(xy=[rectangle[0],rectangle[1]], fill=rectangle[2])     
        return image
    
    def draw_rectangles_on_graph(self):
        '''Draws all rectangles in the rectangles deque to the graph in the correct scale'''
        new_rectangles= deque (())
        
        for rectangle in self.rectangles:
                factor=ImageContainer.zoom_factor/100
                scaled_start_point = [int(x * factor) for x in rectangle[0]] 
                scaled_end_point = [int(x * factor) for x in rectangle[1]] 
                fill= rectangle[2]
                factor=ImageContainer.zoom_factor/100
                               
                rectangle_id = window['-GRAPH-'].draw_rectangle(
                    (scaled_start_point[0],-scaled_start_point[1]),
                    (scaled_end_point[0],-scaled_end_point[1]),
                    fill_color = fill,
                    line_color = fill,
                    line_width = None)
                
                new_rectangles.append((rectangle[0], rectangle[1], fill, rectangle_id))
        
        self.rectangles = new_rectangles
                
    def draw_rectangle(self, start_point, end_point, fill='black'):
        '''Draw a rectangle on graph and add it to the rectangles deque'''
        try:

            factor=ImageContainer.zoom_factor/100

            computed_startpoint_x = int((start_point[0]-self.delta_x) / factor)
            computed_startpoint_y = int((start_point[1]+self.delta_y) / factor)
            
            computed_endpoint_x = int((end_point[0]-self.delta_x) / factor)
            computed_endpoint_y = int((end_point[1]+self.delta_y) / factor)
            
            start_point_in_original = (computed_startpoint_x ,computed_startpoint_y)
            end_point_in_original = (computed_endpoint_x ,computed_endpoint_y )
            
            
            rectangle_id = window['-GRAPH-'].draw_rectangle(
                        (start_point[0],-start_point[1]),
                        (end_point[0],-end_point[1]),
                        fill_color = fill,
                        line_color = fill,
                        line_width = None)
            self.rectangles.append((start_point_in_original, end_point_in_original, fill, rectangle_id))
            
        except ValueError:
            pass
        return self
  
def configure_canvas(event, canvas, frame_id):
    '''Adjust canvas size. Necessary to update scrollbars.'''
    try:
        canvas.itemconfig(frame_id, width=images[current_page].scaled_image.width+40)
    except IndexError:
        pass
    
def configure_frame(event, canvas):
    '''Adjust scrollregion. Necessary to update scrollbars.'''
    canvas.configure(scrollregion=canvas.bbox("all"))

def to_bytes(image):
    '''Convert PIL image to String (base64 encoded PNG)'''
    with io.BytesIO() as output:
        image.save(output, format="PNG")
        return output.getvalue()

def flip_to_page(page):
    '''Update graph with next / previous image. Update page number display.'''
    try:
        page=int(page)
    except ValueError:
        page=0
    if page < 0:
        page=len(images)-1
    if page > len(images)-1:
        page=0
      
    img = images[page]            
    scale_graph_to_image(img.refresh().image)               
    load_image_to_graph(img)
    window['-PAGE_NUM-'].update(value=int(page)+1)
    return page

def draw_character(character, font_path, font_size=25, color='white', width=30, height=30, icon_backgound=False, icon_background_color='dimgray'):
    '''Used to create button icons'''
    # Create image
    image = Image.new("RGBA", (width, height), (255, 0, 125, 0))
    
    # Add a background if used as icon
    if icon_backgound:
        image.paste(round_rectangle((width, height), int(width*0.2), icon_background_color))
    
    # Load font
    font = ImageFont.truetype(font_path, font_size)

    # Draw character
    draw = ImageDraw.Draw(image)
    text1_x, text1_y, text2_x, text2_y  = draw.textbbox([0,0], text=character, font=font)
    x = (width - text2_x - text1_x) // 2
    y = (height - text2_y - text1_y) // 2
    draw.text((x, y), character, font=font, fill=color) 
    return to_bytes(image)
    
def round_corner(radius, fill):
    """Draw a round corner"""
    corner = Image.new('RGBA', (radius, radius), (0, 0, 0, 0))
    draw = ImageDraw.Draw(corner)
    draw.pieslice((0, 0, radius * 2, radius * 2), 180, 270, fill=fill)
    return corner
 
def round_rectangle(size, radius, fill):
    """Draw a rounded rectangle"""
    width, height = size
    rectangle = Image.new('RGBA', size, fill)
    corner = round_corner(radius, fill)
    rectangle.paste(corner, (0, 0))
    rectangle.paste(corner.rotate(90), (0, height - radius)) # Rotate the corner and paste it
    rectangle.paste(corner.rotate(180), (width - radius, height - radius))
    rectangle.paste(corner.rotate(270), (width - radius, 0))
    return rectangle

def load_image_to_graph(image, location=(0,0)):
    '''Loads image to Graph element and adjusts position'''
    window['-GRAPH-'].erase()
    id = window['-GRAPH-'].draw_image(data=image.data(), location=location)

    scale_graph_to_image(image.scaled_image)
    image.draw_rectangles_on_graph()
    window['-GRAPH-'].move(image.delta_x, image.delta_y) 
    image.id = id
    return id

def scale_graph_to_image(image):
    '''Adjust Graph element size to the image (e.g zoom actions)'''
    window['-GRAPH-'].Widget.config(width=image.width, height=image.height)

def toggle_edit_mode(edit_mode='draw'):
    '''Switch mode and set mouse pointer cursor'''
    edit_mode='erase' if edit_mode == 'draw' else 'draw'
    edit_icon = edit_erase_icon if edit_mode == 'erase' else edit_draw_icon
    if edit_mode == 'erase':
        drawing_cursor = 'X_cursor'
    else:
            drawing_cursor = 'crosshair'
    window['-GRAPH-'].set_cursor(drawing_cursor)
    window['EDIT_MODE'].update(data=edit_icon)
    return edit_mode
    
if __name__ == "__main__":
    freeze_support()

    # Needed for pyinstaller onefile...
    try:
        scriptRoot = sys._MEIPASS
    except Exception:
        scriptRoot = os.path.dirname(os.path.realpath(__file__))

    # Initialize
    version = "0.2.0"
    about_text="CoverUP " + version + ''' is free software licensed under the terms of the\nGPL V3.0\n
Visit https://github.com/digidigital/CoverUP or https://coverup.digidigital.de for more information\n
©2023 Björn Seipel -> support@digidigital.de\n
OSS Libraries / modules used by this software:
PySimpleGUI - https://github.com/PySimpleGUI/PySimpleGUI
pypdfium2 - https://github.com/pypdfium2-team/pypdfium2
pyfpdf2 - https://py-pdf.github.io/fpdf2/
Pillow - https://python-pillow.org/
Material Symbols - https://fonts.google.com/icons'''
   
    import_ppi = 150
    pdf = None
    images = []
    fill_color='black'
    current_page = 0
    drawing = False
    start_point = end_point = None
    fontpath = os.path.join(scriptRoot, 'Fonts', 'MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].ttf')
    left = ''
    right = ''
    zoom_in = ''
    zoom_out = ''
    close = ''
    save_pdf = ''
    open_file = ''
    undo = ''
    about = ''
    marker = ''
    eraser_off =''
    eraser =''
    inkdrop_white = ''
    inkdrop_black = ''
    cut = ''
    low_quality = ''
    high_quality = ''
    image_bg_color = 'gray'
    app_icon = draw_character(marker, fontpath, font_size=110, width=128, height=128, icon_backgound=True) 
    low_quality_icon = draw_character(low_quality, fontpath)
    high_quality_icon = draw_character(high_quality, fontpath)
    inkdrop_white_icon = draw_character(inkdrop_white, fontpath)
    inkdrop_black_icon = draw_character(inkdrop_black, fontpath)
    edit_erase_icon = draw_character(eraser, fontpath)
    edit_draw_icon = draw_character(eraser_off, fontpath)
    output_quality = 'high'
    edit_mode = 'draw'
    pointer_cursor = 'arrow' if sg.running_windows() else 'left_ptr'
    drawing_cursor = 'crosshair'
      
    # Layout definition
    graph_layout =[[sg.Graph(canvas_size=(400, 400), background_color='silver', graph_bottom_left=(0,-400), graph_top_right=(400, 0), expand_x=False, expand_y=False, key='-GRAPH-', enable_events=True, drag_submits=True)]]

    layout = [
        [sg.Push(background_color='gray'),sg.Push(background_color='gray'),sg.Push(background_color='gray'),
        sg.Image(draw_character(open_file, fontpath), key="LOAD_PDF", tooltip='Open file', pad=0,  enable_events=True, background_color=image_bg_color),
        sg.Image(draw_character(save_pdf, fontpath), key="SAVE_PDF", tooltip='Save file', pad=0, enable_events=True, background_color=image_bg_color),
        sg.Image(draw_character(cut, fontpath), key="EXPORT_PAGE", tooltip='Export current page', pad=0, enable_events=True, background_color=image_bg_color),
        sg.Push(background_color='gray'),
        sg.Image(draw_character(undo, fontpath), key='UNDO', tooltip='Revert changes', pad=0, enable_events=True, background_color=image_bg_color),
        sg.Image(edit_draw_icon, key="EDIT_MODE", tooltip='Use eraser tool', pad=0, enable_events=True, background_color=image_bg_color),
        sg.Image(inkdrop_black_icon, key='CHANGE_COLOR', tooltip='Switch marker color black/white', pad=0, enable_events=True, background_color=image_bg_color),       
        sg.Image(high_quality_icon, key='TOGGLE_QUALITY', tooltip='Compress output for smaller (low quality) files', pad=0, enable_events=True, background_color=image_bg_color),
        sg.Push(background_color='gray'),
        sg.Image(draw_character(left, fontpath), key='BACK', tooltip='Previous page', pad=0, enable_events=True, background_color=image_bg_color),
        sg.Input(visible=False, focus=True),
        sg.Input(size=(4,2), readonly = False, focus=False, change_submits=False, enable_events=True, justification='center', key='-PAGE_NUM-'),
        sg.Text('/', background_color='gray'),
        sg.Text('0',key='-PAGE_TOTAL-', justification='left', background_color='gray'),
        sg.Image(draw_character(right, fontpath), key='FORTH', tooltip='Next page',pad=0, enable_events=True, background_color=image_bg_color),
        sg.Push(background_color='gray'),
        sg.Image(draw_character(zoom_in, fontpath), key='ZOOM_IN', tooltip='Zoom in', pad=0, enable_events=True, background_color=image_bg_color),
        sg.Image(draw_character(zoom_out, fontpath), key='ZOOM_OUT', tooltip='Zoom out', pad=0, enable_events=True, background_color=image_bg_color),
        sg.Push(background_color='gray'),
        sg.Image(draw_character(about, fontpath), key="ABOUT", tooltip='About CoverUP', pad=0, enable_events=True, background_color=image_bg_color),
        sg.Push(background_color='gray'),sg.Push(background_color='gray'),sg.Push(background_color='gray'),
        ],
        [sg.Column(layout=graph_layout, background_color='silver', size=(800,800), pad=0, expand_x=True, expand_y=True,scrollable=True, sbar_trough_color='lightgrey', sbar_background_color='darkgrey', sbar_relief=sg.RELIEF_RAISED, sbar_arrow_color='silver', key="-GRAPH_COLUMN-")], 
        [sg.ProgressBar(100, key='-PROGRESS-', orientation='horizontal', bar_color=('green','white'), size_px=(50,5), pad=(0,5), expand_x=True)] 
        #[sg.Sizegrip(key='SIZEGRIP')]
    ]
        
    sg.theme('LightBlue2') 

    # Create window
    window = sg.Window('CoverUP', layout, icon=app_icon,element_justification = "center",background_color='grey', size=(1300,950), resizable=True, finalize=True)

    # Detect changes of window size
    frame_id = window['-GRAPH_COLUMN-'].Widget.frame_id
    canvas = window['-GRAPH_COLUMN-'].Widget.canvas
    frame = window['-GRAPH_COLUMN-'].Widget.TKFrame
    window.bind('<Configure>', 'Configure_Event')

    # Alternative binds -> Do not work reliably 
    # canvas.bind("<Configure>", lambda event, canvas=canvas, frame_id=frame_id:configure_canvas(event, canvas, frame_id))
    # frame.bind("<Configure>", lambda event, canvas=canvas:configure_frame(event, canvas))

    while True:

        event, values = window.read()

        if event in (sg.WINDOW_CLOSED, 'EXIT'):
            break
        
        elif event == 'Configure_Event':
            configure_canvas(event, canvas, frame_id)
            configure_frame(event, canvas)
        
        elif event == 'CHANGE_COLOR':
            fill_color='white' if fill_color == 'black' else 'black'
            color_icon = inkdrop_black_icon if fill_color == 'black' else inkdrop_white_icon
            window['CHANGE_COLOR'].update(data=color_icon)
        
        elif event == 'TOGGLE_QUALITY':
            output_quality = 'low' if output_quality == 'high' else 'high'             
            quality_icon = low_quality_icon if output_quality == 'low' else high_quality_icon
            window['TOGGLE_QUALITY'].update(data=quality_icon)
        
        elif event == 'EDIT_MODE':
            edit_mode = toggle_edit_mode(edit_mode)
                
        elif event == 'ABOUT':     
            win_loc_x, win_loc_y = window.current_location()
            win_w, win_h = window.current_size_accurate()
            sg.popup_no_titlebar(about_text, grab_anywhere=False, location=(win_loc_x+win_w/2-185, win_loc_y+win_h/2-200), keep_on_top = True, background_color='silver', button_color='grey')
        
        elif event == 'LOAD_PDF': 
            file_path = sg.PopupGetFile('Load file',  grab_anywhere = True,
        keep_on_top = True, no_window=True, file_types = (('All supported', '*.pdf *.PDF *.jpg *.JPG *.png *.PNG'), ('PDF', '*.pdf *.PDF'),('Image', '*.jpg *.JPG *.png *.PNG')),)
            if file_path :
                try:
                    ImageContainer.zoom_factor=100
                    window.set_cursor('watch')
                    window['-GRAPH-'].set_cursor('watch')
                    window.refresh()
                    # Import PDF files
                    if re.search(".*\.(pdf|PDF)$", file_path):
                        pdf = pdfium.PdfDocument(file_path)
                        total_pages=len(pdf)
                        window['-PAGE_TOTAL-'].update(total_pages) 
                        images=[]
                        for i in range(total_pages):          
                            images.append(ImageContainer(pdf[i].render(scale = int(import_ppi/72)).to_pil(), pdf[i].get_size()))
                            window['-PROGRESS-'].update(current_count=int(i*100/total_pages))
                    
                    # Import single images
                    elif re.search(".*\.(jpg|JPG|png|PNG)$", file_path):
                        window['-PAGE_TOTAL-'].update(1) 
                        images=[]
                        import_image=Image.open(file_path, mode='r')
                        
                        # Fit large images ppi-wise in DIN A4 format with about import_ppi dpi 
                        width, height = import_image.size
                        
                        a4_short_side = round(8.267 * import_ppi)
                        a4_long_side = round(11.693 * import_ppi)
                        
                        
                        # Portrait
                        if height >= width:  
                            if width/height >= 210/297:                  
                                # A4 portrait or short side longer
                                scale_factor= a4_short_side / width
                            else:  
                                # A4 portrait long side longer
                                scale_factor= a4_long_side / height  
                        
                        # Landscape
                        else: 
                            if width/height >= 297/210:
                                # A4 landscape or long side longer
                                scale_factor = a4_long_side / width
                            else:
                                # A4 landscape short side longer
                                scale_factor= a4_short_side / height
                        
                        # Scale images larger as A4 at import_ppi only
                        if scale_factor < 1:        
                            width = int(width * scale_factor)
                            height = int(height * scale_factor)
                            new_image = import_image.resize((width, height), resample=Image.LANCZOS)
                        else:
                            new_image = import_image.copy()
                        
                        import_image.close()
                            
                        # pagesize in ppi @ 72 ppi for pdf output
                        width_ppi=int(width/import_ppi*72)
                        height_ppi=int(height/import_ppi*72)
                        
                        images.append(ImageContainer(new_image, (width_ppi,height_ppi)))
                        
                    else:
                        raise Exception ('The file format %s is not supported!' % file_path.split(".").pop())

                    current_page = 0
                    flip_to_page(current_page)                    
                    window.set_cursor(pointer_cursor)
                    window['-PROGRESS-'].update(current_count=0)
                    window['-GRAPH-'].set_cursor(drawing_cursor)
                except Exception as e:
                    window['-PAGE_TOTAL-'].update('0')
                    window['-PROGRESS-'].update(current_count=0)
                    sg.popup('Ooops! An Error ocurred:', str(e))
                    
        # Actions to be executed only when images / PDF files have benn loaded                        
        elif images:
        
            if event == '-PAGE_NUM-':
                try:
                    page=int(values['-PAGE_NUM-'])
                    current_page = flip_to_page(page-1)
                except ValueError:
                    pass
               
            # Offset actions (not used in final application)
            #      
            #elif event == 'N':
            #    images[current_page].delta_y += 20
            #    window['-GRAPH-'].move(0,20)       
            #
            #elif event == 'O':
            #    images[current_page].delta_x += -20
            #    window['-GRAPH-'].move(-20,0)  
            #
            #elif event == 'S':
            #    images[current_page].delta_y += -20
            #    window['-GRAPH-'].move(0,-20)  
            # 
            #elif event == 'W':
            #    images[current_page].delta_x += 20
            #    window['-GRAPH-'].move(20,0)  
                            
            elif event == 'ZOOM_IN': 
                images[current_page].increase_zoom()
                scale_graph_to_image(images[current_page].scaled_image)
                load_image_to_graph(images[current_page])        

            elif event == 'ZOOM_OUT':
                images[current_page].decrease_zoom()
                scale_graph_to_image(images[current_page].scaled_image)
                load_image_to_graph(images[current_page]) 
            
            elif event == 'FORTH':
                current_page = flip_to_page(current_page + 1)

            elif event == 'BACK':
                current_page = flip_to_page(current_page - 1)
            
            elif event == 'UNDO':
                images[current_page].undo()
                
            elif event == 'SAVE_PDF' or event == 'EXPORT_PAGE':
                file_path = sg.PopupGetFile('Save PDF file', no_window=True, save_as=True, file_types = (('PDF', '*.pdf *.PDF'),), default_extension=".pdf")
                
                if file_path: 
                    try:
                        out_pdf = FPDF(unit="pt")
                        out_pdf.set_creator('CoverUp ' + version)
                        out_pdf.set_creation_date(datetime.today()) 
                        window.set_cursor('watch')
                        window['-GRAPH-'].set_cursor('watch')
                        window.refresh()
                               
                        if event == 'EXPORT_PAGE':
                            out_pdf.add_page(format=[images[current_page].height_in_pt, images[current_page].width_in_pt])
                            # Original image or resized and compressed?
                            include_image = images[current_page].finalized_image() if output_quality == 'high' else images[current_page].finalized_image('JPEG', image_quality=75, scale=0.90)
                            out_pdf.image(include_image, x=0, y=0, w=out_pdf.w)
                        
                        else:
                            itemcount=0
                            for item in images:
                                itemcount+=1
                                window['-PROGRESS-'].update(current_count=int(itemcount*100/len(images)))
                                out_pdf.add_page(format=[item.height_in_pt, item.width_in_pt])
                                # Original image or resized and compressed?
                                #include_image = item.image if output_quality == 'high' else item.jpg(image_quality=55, scale=0.85)
                                include_image = item.finalized_image() if output_quality == 'high' else item.finalized_image('JPEG', image_quality=50, scale=0.80)
                                out_pdf.image(include_image, x=0, y=0, w=out_pdf.w)
                            
                        out_pdf.output(file_path)
                        
                        window['-PROGRESS-'].update(current_count=0)
                        window.set_cursor(pointer_cursor)
                        window['-GRAPH-'].set_cursor(drawing_cursor)
                        
                    except Exception as e:                     
                        window['-PROGRESS-'].update(current_count=0)
                        window.set_cursor(pointer_cursor)
                        window['-GRAPH-'].set_cursor(drawing_cursor)  
                        sg.popup('Ooops! An error occurred: ', str(e))
                        
            # Draw on Graph 
            elif event == '-GRAPH-' and edit_mode == 'draw':
                x, y = values['-GRAPH-']
                y = -y  # Flip y-coordinate
                # Begin drawing
                if not drawing:
                    start_point = (x, y)
                    drawing = True
                
                # Draw a temporary red rectangle during drawing as position indicator
                else:
                    try:
                        window['-GRAPH-'].delete_figure(temp_rectangle)
                    except:
                        pass
                    end_point = (x, y)
                    if start_point[0]<end_point[0] and start_point[1]<end_point[1]:                   
                        temp_rectangle = window['-GRAPH-'].draw_rectangle(
                        (start_point[0],-start_point[1]),
                        (end_point[0],-end_point[1]),
                        fill_color = 'red',
                        line_color = 'red',
                        line_width = None)
  
            # Conclude drawing             
            elif event == '-GRAPH-+UP' and images:
                drawing = False
                x, y = values['-GRAPH-']
                
                if edit_mode == 'draw':
                    try:
                        window['-GRAPH-'].delete_figure(temp_rectangle)
                    except:
                        pass
                    if start_point[0]<end_point[0] and start_point[1]<end_point[1]: 
                        y = -y  # Flip y-coordinate 
                        end_point = (x, y)                     

                        images[current_page].draw_rectangle(start_point, end_point, fill=fill_color)
                
                elif edit_mode == 'erase':
                    figures = window['-GRAPH-'].get_figures_at_location((x,y))
                    edit_mode = toggle_edit_mode(edit_mode)
                    if len(figures) > 1 and len(images[current_page].rectangles) > 0:
                        window['-GRAPH-'].delete_figure(figures[-1])
                        images[current_page].rectangles = [item for item in images[current_page].rectangles if item[3] != figures[-1] ]
                        
    window.close()
