#alright here we go #dee da dee da deedy do do

a = open("out.txt","w")
b = open("out2.txt","w")
c= open("out3.txt","w")

type = "gs"

y = []
z = []
i = []
letter = ["B","D","F","H","J","L"]
adj_letter = ["A","C","E","G","I","K"]
let_ind = 1
start = ["14","27","39"]
start_ind = 0

if type == "const_plane":
    for x in range(14):
        ind = str(x+1)
        ind2 = str(24+x*12)

        y.append("=IF(Sheet1!$B$5>"+ind+',\"LIST\",\"\") \n')
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"def_type\",\"\") \n")
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"orbit_indx\",\"\") \n")
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"plane_def\",\"\") \n")
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"plane_def\",\"\") \n")
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"plane_def\",\"\") \n")
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"plane_def\",\"\") \n")
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"plane_def\",\"\") \n")
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"first_M_deg\",\"\") \n")
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"spacing_type\",\"\") \n")
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"first_sat_id\",\"\") \n")
        y.append("=IF(NOT($A"+ind2+"=\"\"),\"sats_in_plane\",\"\") \n")

        #second column
        z.append("=IF(Sheet1!$B$5>"+ind+',\"LIST\",\"\") \n')
        z.append("=IF(NOT($A"+ind2+"=\"\"),\"plane\",\"\") \n")
        z.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+start[start_ind]+",\"\") \n")
        z.append("=IF(NOT($A"+ind2+"=\"\"),\"a_km\",\"\") \n")
        z.append("=IF(NOT($A"+ind2+"=\"\"),\"e\",\"\") \n")
        z.append("=IF(NOT($A"+ind2+"=\"\"),\"i_deg\",\"\") \n")
        z.append("=IF(NOT($A"+ind2+"=\"\"),\"RAAN_deg\",\"\") \n")
        z.append("=IF(NOT($A"+ind2+"=\"\"),\"arg_per_deg\",\"\") \n")
        z.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+6)+",\"\") \n") #20
        z.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+10)+",\"\") \n")
        z.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+9)+",\"\") \n")
        z.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+8)+",\"\") \n")

        #third column
        i.append("=IF(Sheet1!$B$5>"+ind+',\"LIST\",\"\") \n')
        i.append("\n")
        i.append("\n")
        i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+1)+",\"\") \n")
        i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+2)+",\"\") \n")
        i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+3)+",\"\") \n")
        i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+4)+",\"\") \n")
        i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+5)+",\"\") \n")
        i.append("\n")
        i.append("\n")
        i.append("\n")
        i.append("\n")

        let_ind += 1
        if let_ind > 4:
            let_ind = 0
            start_ind += 1 
elif type =="const_indiv":
    for x in range(14):
            ind = str(x+1)
            ind2 = str(21+x*9)

            y.append("=IF(Sheet1!$B$5>"+ind+',\"LIST\",\"\") \n')
            y.append("=IF(NOT($A"+ind2+"=\"\"),\"sat_id\",\"\") \n")
            y.append("=IF(NOT($A"+ind2+"=\"\"),\"def_type\",\"\") \n")
            y.append("=IF(NOT($A"+ind2+"=\"\"),\"kepler_meananom\",\"\") \n")
            y.append("=IF(NOT($A"+ind2+"=\"\"),\"kepler_meananom\",\"\") \n")
            y.append("=IF(NOT($A"+ind2+"=\"\"),\"kepler_meananom\",\"\") \n")
            y.append("=IF(NOT($A"+ind2+"=\"\"),\"kepler_meananom\",\"\") \n")
            y.append("=IF(NOT($A"+ind2+"=\"\"),\"kepler_meananom\",\"\") \n")
            y.append("=IF(NOT($A"+ind2+"=\"\"),\"kepler_meananom\",\"\") \n")

            #second column
            z.append("=IF(Sheet1!$B$5>"+ind+',\"LIST\",\"\") \n')
            z.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+adj_letter[let_ind]+"$"+start[start_ind]+",\"\") \n")
            z.append("=IF(NOT($A"+ind2+"=\"\"),\"indiv\",\"\") \n")
            z.append("=IF(NOT($A"+ind2+"=\"\"),\"a_km\",\"\") \n")
            z.append("=IF(NOT($A"+ind2+"=\"\"),\"e\",\"\") \n")
            z.append("=IF(NOT($A"+ind2+"=\"\"),\"i_deg\",\"\") \n")
            z.append("=IF(NOT($A"+ind2+"=\"\"),\"RAAN_deg\",\"\") \n")
            z.append("=IF(NOT($A"+ind2+"=\"\"),\"arg_per_deg\",\"\") \n")
            z.append("=IF(NOT($A"+ind2+"=\"\"),\"M_deg\",\"\") \n")

            #third column
            i.append("=IF(Sheet1!$B$5>"+ind+',\"LIST\",\"\") \n')
            i.append("\n")
            i.append("\n")
            i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+1)+",\"\") \n")
            i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+2)+",\"\") \n")
            i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+3)+",\"\") \n")
            i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+4)+",\"\") \n")
            i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+5)+",\"\") \n")
            i.append("=IF(NOT($A"+ind2+"=\"\"),Sheet1!"+letter[let_ind]+"$"+str(int(start[start_ind])+6)+",\"\") \n")

            let_ind += 1
            if let_ind > 4:
                let_ind = 0
                start_ind += 1 
elif type =="gs":
    let_ind =0
    counter = 0
    for x in range(18):
        if counter < 6:
            ind2 = 14
        elif counter < 11:
            ind2 = 23
        else:
            ind2 = 32
        counter +=1
        ind = str(x)

        y.append("=IF($D$6>"+ind+',\"LIST\",\"\") \n')
        y.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + adj_letter[let_ind]+str(ind2)+"),\"\") \n")
        y.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + adj_letter[let_ind]+str(ind2+1)+"),\"\") \n")
        y.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + adj_letter[let_ind]+str(ind2+2)+"),\"\") \n")
        y.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + adj_letter[let_ind]+str(ind2+3)+"),\"\") \n")
        y.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + adj_letter[let_ind]+str(ind2+4)+"),\"\") \n")
        y.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + adj_letter[let_ind]+str(ind2+5)+"),\"\") \n")
        y.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + adj_letter[let_ind]+str(ind2+6)+"),\"\") \n")
        

        z.append("=IF($D$6>"+ind+',\"LIST\",\"\") \n')
        z.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + letter[let_ind]+str(ind2)+"),\"\") \n")
        z.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + letter[let_ind]+str(ind2+1)+"),\"\") \n")
        z.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + letter[let_ind]+str(ind2+2)+"),\"\") \n")
        z.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + letter[let_ind]+str(ind2+3)+"),\"\") \n")
        z.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + letter[let_ind]+str(ind2+4)+"),\"\") \n")
        z.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + letter[let_ind]+str(ind2+5)+"),\"\") \n")
        z.append("=IF($D$6>"+ind+",LOWER(Sheet1!" + letter[let_ind]+str(ind2+6)+"),\"\") \n")

        i.append("=IF($D$6>"+ind+',\"LIST\",\"\") \n')
        i.append("\n")
        i.append("\n")
        i.append("\n")
        i.append("\n")
        i.append("\n")
        i.append("\n")
        i.append("\n")

        let_ind +=1
        if let_ind > 5:
            let_ind = 0

a.writelines(y)
b.writelines(z)
c.writelines(i)