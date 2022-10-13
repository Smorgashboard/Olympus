
### lets get some basic info for the start of the program
input_string = input("Inscope urls seperated by a colon no space: ")
scoped_urls = input_string.split(":")

boolAPP = input("APK? 1 for Yes or 0 for No.")
if boolAPP == 1:
    input_android_apk_url = input("Download url for APK")

boolUploadSQL = input("Should I upload to SQL? 1 for Yes or 0 for No.")